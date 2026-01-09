"""
Binance Data Enrichment Layer
Enhances MT5 indicator data with real-time Binance microstructure.

Purpose:
- Provides faster price updates (1s vs MT5's 1min)
- Adds order flow insights (if depth stream enabled)
- Validates MT5 data against Binance feed
- Enriches decision engine with real-time context

Usage:
    enricher = BinanceEnrichment(binance_service, mt5_service)
    enriched_m5 = enricher.enrich_timeframe("BTCUSDT", mt5_m5_data, "M5")
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class BinanceEnrichment:
    """
    Enriches MT5 indicator data with real-time Binance microstructure.
    """
    
    def __init__(self, binance_service=None, mt5_service=None, order_flow_service=None):
        """
        Args:
            binance_service: BinanceService instance (optional)
            mt5_service: MT5Service instance (optional)
            order_flow_service: OrderFlowService instance (optional)
        """
        self.binance_service = binance_service
        self.mt5_service = mt5_service
        self.order_flow_service = order_flow_service
        
    def enrich_timeframe(
        self,
        symbol: str,
        mt5_data: Dict,
        timeframe: str = "M5"
    ) -> Dict:
        """
        Enrich MT5 indicator data with Binance real-time data.
        
        Args:
            symbol: Trading symbol (MT5 format, e.g., "BTCUSDc")
            mt5_data: Dictionary of MT5 indicators
            timeframe: Timeframe being enriched (M5, M15, etc.)
            
        Returns:
            Enriched dictionary with additional fields:
            - binance_price: Current Binance price
            - binance_age: Age of Binance data in seconds
            - feed_health: Binance feed health status
            - price_velocity: Short-term price momentum
            - micro_spread: Binance spread (if available)
        """
        if not self.binance_service or not self.binance_service.running:
            # No Binance data available - return MT5 data as-is
            return mt5_data.copy()
            
        try:
            # Get latest Binance tick
            binance_tick = self.binance_service.get_latest_tick(symbol)
            
            if not binance_tick:
                return mt5_data.copy()
                
            # Create enriched copy
            enriched = mt5_data.copy()
            
            # Add Binance price
            enriched['binance_price'] = binance_tick['price']
            enriched['binance_age'] = self.binance_service.cache.get_age_seconds(
                self.binance_service._convert_to_binance_symbol(symbol)
            )
            
            # Add feed health
            health = self.binance_service.get_feed_health(symbol)
            enriched['feed_health'] = health.get('overall_status', 'unknown')
            
            # Calculate price velocity (last 5 ticks)
            history = self.binance_service.get_history(symbol, count=5)
            if len(history) >= 2:
                prices = [t['price'] for t in history]
                velocity = (prices[-1] - prices[0]) / len(prices)
                enriched['price_velocity'] = velocity
            else:
                enriched['price_velocity'] = 0.0
                
            # Add micro momentum (last 10 ticks)
            history = self.binance_service.get_history(symbol, count=10)
            if len(history) >= 10:
                prices = [t['price'] for t in history]
                enriched['micro_momentum'] = self._calculate_micro_momentum(prices)
            else:
                enriched['micro_momentum'] = 0.0
                
            # Add real-time volume trend (last 20 ticks)
            history = self.binance_service.get_history(symbol, count=20)
            if len(history) >= 20:
                volumes = [t['volume'] for t in history]
                enriched['volume_acceleration'] = self._calculate_volume_accel(volumes)
            else:
                enriched['volume_acceleration'] = 0.0
            
            # NEW: Add more contextual data for better analysis
            history = self.binance_service.get_history(symbol, count=30)
            if len(history) >= 30:
                prices = [t['price'] for t in history]
                
                # Price trend analysis (last 10s)
                recent_prices = prices[-10:]
                enriched['price_trend_10s'] = self._get_price_trend(recent_prices)
                
                # Price volatility
                enriched['price_volatility'] = self._calculate_volatility(prices)
                
                # Volume surge detection
                volumes = [t['volume'] for t in history]
                enriched['volume_surge'] = self._detect_volume_surge(volumes)
                
                # Momentum acceleration (is momentum increasing or decreasing?)
                enriched['momentum_acceleration'] = self._calculate_momentum_acceleration(prices)
                
                # Divergence vs MT5 (if MT5 price available)
                if 'close' in mt5_data:
                    mt5_price = mt5_data['close']
                    binance_price = binance_tick['price']
                    divergence_pct = abs((binance_price - mt5_price) / mt5_price) * 100
                    enriched['divergence_vs_mt5'] = divergence_pct > 0.05  # More than 0.05% divergence
                    enriched['divergence_pct'] = divergence_pct
                else:
                    enriched['divergence_vs_mt5'] = False
                    enriched['divergence_pct'] = 0.0
                
                # Candle context (last completed candle)
                if len(history) >= 2:
                    last_candle = history[-2]  # Use previous candle (completed)
                    open_price = last_candle.get('open', last_candle['price'])
                    close_price = last_candle.get('close', last_candle['price'])
                    high_price = last_candle.get('high', last_candle['price'])
                    low_price = last_candle.get('low', last_candle['price'])
                    
                    enriched['last_candle_color'] = "GREEN" if close_price > open_price else "RED"
                    
                    body = abs(close_price - open_price)
                    total_range = high_price - low_price
                    
                    if total_range > 0:
                        body_pct = (body / total_range) * 100
                        enriched['last_candle_size'] = "LARGE" if body_pct > 60 else "MEDIUM" if body_pct > 30 else "SMALL"
                        
                        # Wick analysis
                        upper_wick = high_price - max(open_price, close_price)
                        lower_wick = min(open_price, close_price) - low_price
                        
                        enriched['wicks'] = {
                            'upper_wick_ratio': (upper_wick / total_range) if total_range > 0 else 0,
                            'lower_wick_ratio': (lower_wick / total_range) if total_range > 0 else 0
                        }
                    else:
                        enriched['last_candle_size'] = "DOJI"
                        enriched['wicks'] = {'upper_wick_ratio': 0, 'lower_wick_ratio': 0}
            
            # 🔥 TOP 5 HIGH-VALUE ENRICHMENTS
            if len(history) >= 30:
                prices = [t['price'] for t in history]
                volumes = [t['volume'] for t in history]
                
                # 1. Higher High / Lower Low Detection
                hh_ll_data = self._detect_price_structure(prices)
                enriched['price_structure'] = hh_ll_data['structure']
                enriched['structure_strength'] = hh_ll_data['strength']
                enriched['consecutive_structures'] = hh_ll_data['consecutive_count']
                
                # 2. Volatility Expansion/Contraction
                vol_state = self._detect_volatility_state(prices)
                enriched['volatility_state'] = vol_state['state']
                enriched['volatility_change_pct'] = vol_state['change_pct']
                enriched['squeeze_duration'] = vol_state.get('squeeze_duration', 0)
                
                # 3. Momentum Consistency
                momentum_quality = self._calculate_momentum_consistency(prices)
                enriched['momentum_consistency'] = momentum_quality['consistency_score']
                enriched['consecutive_moves'] = momentum_quality['consecutive_moves']
                enriched['momentum_quality'] = momentum_quality['quality_label']
                
                # 4. Spread Trend (if tick data available with bid/ask)
                # Note: Binance kline data doesn't have bid/ask, so we'll estimate from price movement
                spread_analysis = self._analyze_spread_proxy(prices)
                enriched['spread_trend'] = spread_analysis['trend']
                enriched['price_choppiness'] = spread_analysis['choppiness']
                
                # 5. Micro Timeframe Alignment
                mtf_alignment = self._calculate_micro_alignment(prices)
                enriched['micro_alignment'] = mtf_alignment['alignment']
                enriched['micro_alignment_score'] = mtf_alignment['score']
                enriched['alignment_strength'] = mtf_alignment['strength']
                
                # 🔥 PHASE 2A: 6 MORE HIGH-VALUE ENRICHMENTS
                
                # 6. Support/Resistance Touch Count
                key_level = self._detect_key_level(prices)
                if key_level:
                    enriched['key_level'] = key_level
                
                # 7. Momentum Divergence (Price vs Volume)
                divergence = self._detect_momentum_divergence(prices, volumes)
                enriched['momentum_divergence'] = divergence['type']
                enriched['divergence_strength'] = divergence['strength']
                
                # 8. Real-Time ATR
                rt_atr = self._calculate_realtime_atr(prices)
                enriched['binance_atr'] = rt_atr['atr']
                if 'atr_14' in mt5_data:
                    mt5_atr = mt5_data['atr_14']
                    divergence_pct = ((rt_atr['atr'] - mt5_atr) / mt5_atr) * 100 if mt5_atr > 0 else 0
                    enriched['atr_divergence_pct'] = divergence_pct
                    enriched['atr_state'] = "HIGHER" if divergence_pct > 10 else "LOWER" if divergence_pct < -10 else "ALIGNED"
                else:
                    enriched['atr_divergence_pct'] = 0
                    enriched['atr_state'] = "UNKNOWN"
                
                # 9. Bollinger Band Position
                bb_data = self._calculate_bollinger_bands(prices)
                enriched['bb_position'] = bb_data['position']
                enriched['bb_width_pct'] = bb_data['width_pct']
                enriched['bb_squeeze'] = bb_data['squeeze']
                
                # 10. Speed of Move
                speed_data = self._calculate_move_speed(prices)
                enriched['move_speed'] = speed_data['speed']
                enriched['speed_percentile'] = speed_data['percentile']
                enriched['speed_warning'] = speed_data['warning']
                
                # 11. Momentum-Volume Alignment
                mv_alignment = self._calculate_momentum_volume_alignment(prices, volumes)
                enriched['momentum_volume_alignment'] = mv_alignment['score']
                enriched['mv_alignment_quality'] = mv_alignment['quality']
                enriched['volume_confirmation'] = mv_alignment['confirmed']
                
                # 🔥 PHASE 2B: 7 MORE ADVANCED ENRICHMENTS
                
                # 12. Tick Frequency (Activity Level)
                tick_freq = self._calculate_tick_frequency(history)
                enriched['tick_frequency'] = tick_freq['ticks_per_sec']
                enriched['tick_activity'] = tick_freq['activity_level']
                enriched['tick_percentile'] = tick_freq['percentile']
                
                # 13. Price Z-Score (Mean Reversion)
                z_score_data = self._calculate_price_zscore(prices)
                enriched['price_zscore'] = z_score_data['zscore']
                enriched['zscore_extremity'] = z_score_data['extremity']
                enriched['mean_reversion_signal'] = z_score_data['signal']
                
                # 14. Pivot Points (Intraday Targets)
                pivots = self._calculate_pivot_points(prices)
                enriched['pivot_data'] = pivots
                enriched['price_vs_pivot'] = pivots['position']
                
                # 15. Tape Reading (Aggressor Side)
                # Note: Requires trade data with buyer_maker flag
                # For now, we'll infer from price movement and volume
                tape_data = self._analyze_tape_reading(prices, volumes)
                enriched['aggressor_side'] = tape_data['aggressor']
                enriched['aggressor_strength'] = tape_data['strength']
                enriched['tape_dominance'] = tape_data['dominance']
                
                # 16. Liquidity Depth Score
                # Uses price volatility as proxy for liquidity
                liquidity_score = self._calculate_liquidity_score(prices, volumes)
                enriched['liquidity_score'] = liquidity_score['score']
                enriched['liquidity_quality'] = liquidity_score['quality']
                enriched['execution_confidence'] = liquidity_score['exec_confidence']
                
                # 17. Time-of-Day Context
                tod_context = self._get_time_of_day_context(symbol)
                enriched['hour_of_day'] = tod_context['hour']
                enriched['session'] = tod_context['session']
                enriched['volatility_vs_typical'] = tod_context['vol_comparison']
                
                # 18. Candle Pattern Recognition
                pattern = self._detect_candle_pattern(prices, volumes)
                enriched['candle_pattern'] = pattern['pattern']
                enriched['pattern_confidence'] = pattern['confidence']
                enriched['pattern_direction'] = pattern['direction']
            
            # Add order flow data (if available)
            if self.order_flow_service and self.order_flow_service.running:
                try:
                    # Convert MT5 symbol (e.g., "BTCUSDc") to Binance symbol (e.g., "btcusdt")
                    binance_symbol = symbol.upper()
                    if binance_symbol.endswith('C'):
                        binance_symbol = binance_symbol[:-1]  # Remove 'c' suffix
                    # Convert to Binance format (BTCUSD -> btcusdt for crypto, others lowercase)
                    if binance_symbol.startswith(('BTC', 'ETH', 'LTC', 'XRP', 'ADA')):
                        if not binance_symbol.endswith('USDT'):
                            binance_symbol = binance_symbol.replace('USD', 'USDT')
                    binance_symbol = binance_symbol.lower()
                    
                    order_flow = self.order_flow_service.get_order_flow_signal(binance_symbol)
                    if order_flow and isinstance(order_flow, dict):
                        # Safely extract nested values with proper defaults
                        order_book = order_flow.get('order_book') or {}
                        whale_activity = order_flow.get('whale_activity') or {}
                        pressure = order_flow.get('pressure') or {}
                        
                        enriched['order_flow'] = {
                            'signal': order_flow.get('signal', 'NEUTRAL'),
                            'confidence': order_flow.get('confidence', 0),
                            'imbalance': order_book.get('imbalance'),
                            'whale_count': whale_activity.get('total_whales', 0),
                            'pressure_side': pressure.get('dominant_side', 'NEUTRAL'),
                            'liquidity_voids': len(order_flow.get('liquidity_voids', [])),
                            'warnings': order_flow.get('warnings', [])
                        }
                        logger.debug(f"Added order flow data to {symbol} {timeframe}")
                except Exception as e:
                    logger.warning(f"Failed to add order flow data: {e}", exc_info=True)
                
            logger.debug(f"Enriched {symbol} {timeframe} with Binance data")
            
            return enriched
            
        except Exception as e:
            logger.warning(f"Failed to enrich {symbol} with Binance data: {e}")
            return mt5_data.copy()
            
    def _calculate_micro_momentum(self, prices: list) -> float:
        """
        Calculate micro-momentum from recent price history.
        
        Returns:
            Positive = bullish momentum, Negative = bearish momentum
        """
        if len(prices) < 2:
            return 0.0
            
        # Simple linear regression slope
        x = np.arange(len(prices))
        y = np.array(prices)
        
        # Normalize to percentage
        mean_price = np.mean(y)
        if mean_price == 0:
            return 0.0
            
        slope = np.polyfit(x, y, 1)[0]
        return (slope / mean_price) * 100  # Convert to percentage
        
    def _calculate_volume_accel(self, volumes: list) -> float:
        """
        Calculate volume acceleration (increasing or decreasing).
        
        Returns:
            Positive = volume increasing, Negative = volume decreasing
        """
        if len(volumes) < 10:
            return 0.0
            
        # Compare recent half vs older half
        mid = len(volumes) // 2
        recent_avg = np.mean(volumes[mid:])
        older_avg = np.mean(volumes[:mid])
        
        if older_avg == 0:
            return 0.0
            
        return ((recent_avg - older_avg) / older_avg) * 100
    
    def _get_price_trend(self, prices: list) -> str:
        """Determine price trend from recent prices"""
        if len(prices) < 3:
            return "FLAT"
        
        # Compare first third vs last third
        third = len(prices) // 3
        start_avg = np.mean(prices[:third])
        end_avg = np.mean(prices[-third:])
        
        change_pct = ((end_avg - start_avg) / start_avg) * 100 if start_avg > 0 else 0
        
        if change_pct > 0.05:
            return "RISING"
        elif change_pct < -0.05:
            return "FALLING"
        else:
            return "FLAT"
    
    def _calculate_volatility(self, prices: list) -> float:
        """Calculate price volatility (standard deviation)"""
        if len(prices) < 2:
            return 0.0
        
        std_dev = np.std(prices)
        mean_price = np.mean(prices)
        
        if mean_price == 0:
            return 0.0
        
        # Return as percentage of mean
        return (std_dev / mean_price) * 100
    
    def _detect_volume_surge(self, volumes: list) -> bool:
        """Detect if volume is surging"""
        if len(volumes) < 10:
            return False
        
        # Compare last 3 ticks vs average of previous 7
        recent = np.mean(volumes[-3:])
        baseline = np.mean(volumes[-10:-3])
        
        if baseline == 0:
            return False
        
        # Surge if recent volume is 2x baseline
        return recent > (baseline * 2.0)
    
    def _calculate_momentum_acceleration(self, prices: list) -> float:
        """
        Calculate if momentum is accelerating (positive) or decelerating (negative).
        
        Returns:
            Positive = momentum increasing, Negative = momentum decreasing
        """
        if len(prices) < 20:
            return 0.0
        
        # Calculate momentum for two halves
        mid = len(prices) // 2
        
        # First half momentum
        first_half = prices[:mid]
        if len(first_half) >= 2:
            first_momentum = self._calculate_micro_momentum(first_half)
        else:
            first_momentum = 0.0
        
        # Second half momentum
        second_half = prices[mid:]
        if len(second_half) >= 2:
            second_momentum = self._calculate_micro_momentum(second_half)
        else:
            second_momentum = 0.0
        
        # Acceleration is the change in momentum
        return second_momentum - first_momentum
    
    def _detect_price_structure(self, prices: list) -> dict:
        """
        Detect Higher High / Lower Low / Higher Low / Lower High patterns.
        
        Returns:
            {
                'structure': "HIGHER_HIGH" | "HIGHER_LOW" | "LOWER_HIGH" | "LOWER_LOW" | "EQUAL" | "CHOPPY",
                'strength': 0-100,
                'consecutive_count': int
            }
        """
        if len(prices) < 15:
            return {'structure': "UNKNOWN", 'strength': 0, 'consecutive_count': 0}
        
        # Divide into 5-tick segments and find highs/lows
        segment_size = 5
        segments = []
        for i in range(0, len(prices) - segment_size + 1, segment_size):
            segment = prices[i:i + segment_size]
            segments.append({
                'high': max(segment),
                'low': min(segment),
                'close': segment[-1]
            })
        
        if len(segments) < 3:
            return {'structure': "UNKNOWN", 'strength': 0, 'consecutive_count': 0}
        
        # Compare last 3 segments
        recent = segments[-3:]
        
        # Check for Higher Highs
        highs = [s['high'] for s in recent]
        lows = [s['low'] for s in recent]
        
        # Higher High: Each high > previous high
        if highs[-1] > highs[-2] > highs[-3]:
            strength = min(100, int(((highs[-1] - highs[-3]) / highs[-3]) * 10000))
            consecutive = 2  # Two consecutive higher highs
            for i in range(len(segments) - 4, -1, -1):
                if segments[i]['high'] < segments[i+1]['high']:
                    consecutive += 1
                else:
                    break
            return {'structure': "HIGHER_HIGH", 'strength': strength, 'consecutive_count': consecutive}
        
        # Higher Low: Each low > previous low (bullish structure)
        elif lows[-1] > lows[-2] > lows[-3]:
            strength = min(100, int(((lows[-1] - lows[-3]) / lows[-3]) * 10000))
            consecutive = 2
            for i in range(len(segments) - 4, -1, -1):
                if segments[i]['low'] < segments[i+1]['low']:
                    consecutive += 1
                else:
                    break
            return {'structure': "HIGHER_LOW", 'strength': strength, 'consecutive_count': consecutive}
        
        # Lower High: Each high < previous high (bearish structure)
        elif highs[-1] < highs[-2] < highs[-3]:
            strength = min(100, int(((highs[-3] - highs[-1]) / highs[-3]) * 10000))
            consecutive = 2
            for i in range(len(segments) - 4, -1, -1):
                if segments[i]['high'] > segments[i+1]['high']:
                    consecutive += 1
                else:
                    break
            return {'structure': "LOWER_HIGH", 'strength': strength, 'consecutive_count': consecutive}
        
        # Lower Low: Each low < previous low
        elif lows[-1] < lows[-2] < lows[-3]:
            strength = min(100, int(((lows[-3] - lows[-1]) / lows[-3]) * 10000))
            consecutive = 2
            for i in range(len(segments) - 4, -1, -1):
                if segments[i]['low'] > segments[i+1]['low']:
                    consecutive += 1
                else:
                    break
            return {'structure': "LOWER_LOW", 'strength': strength, 'consecutive_count': consecutive}
        
        # Equal highs/lows (consolidation)
        elif abs(highs[-1] - highs[-2]) / highs[-2] < 0.001 and abs(lows[-1] - lows[-2]) / lows[-2] < 0.001:
            return {'structure': "EQUAL", 'strength': 50, 'consecutive_count': 1}
        
        else:
            return {'structure': "CHOPPY", 'strength': 25, 'consecutive_count': 0}
    
    def _detect_volatility_state(self, prices: list) -> dict:
        """
        Detect if volatility is expanding, contracting, or stable.
        
        Returns:
            {
                'state': "EXPANDING" | "CONTRACTING" | "STABLE",
                'change_pct': float,
                'squeeze_duration': int (seconds in contraction)
            }
        """
        if len(prices) < 20:
            return {'state': "UNKNOWN", 'change_pct': 0}
        
        # Calculate volatility for two halves
        mid = len(prices) // 2
        first_half = prices[:mid]
        second_half = prices[mid:]
        
        vol_first = np.std(first_half) if len(first_half) > 1 else 0
        vol_second = np.std(second_half) if len(second_half) > 1 else 0
        
        if vol_first == 0:
            return {'state': "UNKNOWN", 'change_pct': 0}
        
        change_pct = ((vol_second - vol_first) / vol_first) * 100
        
        # Determine state
        if change_pct > 20:
            state = "EXPANDING"
        elif change_pct < -20:
            state = "CONTRACTING"
            # Estimate squeeze duration (simplified)
            squeeze_duration = len(prices)  # Seconds
            return {'state': state, 'change_pct': change_pct, 'squeeze_duration': squeeze_duration}
        else:
            state = "STABLE"
        
        return {'state': state, 'change_pct': change_pct}
    
    def _calculate_momentum_consistency(self, prices: list) -> dict:
        """
        Calculate how consistent momentum is (non-choppy).
        
        Returns:
            {
                'consistency_score': 0-100,
                'consecutive_moves': int,
                'quality_label': "EXCELLENT" | "GOOD" | "FAIR" | "CHOPPY"
            }
        """
        if len(prices) < 10:
            return {'consistency_score': 0, 'consecutive_moves': 0, 'quality_label': "UNKNOWN"}
        
        # Calculate tick-by-tick moves
        moves = []
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                moves.append(1)  # Up
            elif prices[i] < prices[i-1]:
                moves.append(-1)  # Down
            else:
                moves.append(0)  # Flat
        
        if not moves:
            return {'consistency_score': 0, 'consecutive_moves': 0, 'quality_label': "UNKNOWN"}
        
        # Count consecutive moves in same direction
        max_consecutive = 1
        current_consecutive = 1
        for i in range(1, len(moves)):
            if moves[i] == moves[i-1] and moves[i] != 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 1
        
        # Calculate consistency score
        # Score = % of moves in dominant direction
        up_moves = sum(1 for m in moves if m > 0)
        down_moves = sum(1 for m in moves if m < 0)
        dominant_moves = max(up_moves, down_moves)
        
        consistency_score = int((dominant_moves / len(moves)) * 100)
        
        # Quality label
        if consistency_score >= 80:
            quality_label = "EXCELLENT"
        elif consistency_score >= 65:
            quality_label = "GOOD"
        elif consistency_score >= 50:
            quality_label = "FAIR"
        else:
            quality_label = "CHOPPY"
        
        return {
            'consistency_score': consistency_score,
            'consecutive_moves': max_consecutive,
            'quality_label': quality_label
        }
    
    def _analyze_spread_proxy(self, prices: list) -> dict:
        """
        Analyze price choppiness as a proxy for spread (since we don't have bid/ask).
        
        Returns:
            {
                'trend': "WIDENING" | "NARROWING" | "STABLE",
                'choppiness': 0-100 (100 = very choppy)
            }
        """
        if len(prices) < 20:
            return {'trend': "UNKNOWN", 'choppiness': 0}
        
        # Calculate choppiness: how much price zig-zags vs net movement
        net_movement = abs(prices[-1] - prices[0])
        total_movement = sum(abs(prices[i] - prices[i-1]) for i in range(1, len(prices)))
        
        if net_movement == 0:
            choppiness = 100
        else:
            # Choppiness ratio: total movement / net movement
            # Low ratio = trending, high ratio = choppy
            ratio = total_movement / net_movement if net_movement > 0 else 100
            choppiness = min(100, int((ratio - 1) * 20))  # Scale to 0-100
        
        # Compare first half vs second half choppiness
        mid = len(prices) // 2
        first_half = prices[:mid]
        second_half = prices[mid:]
        
        def calc_chop(prices_segment):
            if len(prices_segment) < 2:
                return 0
            net = abs(prices_segment[-1] - prices_segment[0])
            total = sum(abs(prices_segment[i] - prices_segment[i-1]) for i in range(1, len(prices_segment)))
            return total / net if net > 0 else 100
        
        chop_first = calc_chop(first_half)
        chop_second = calc_chop(second_half)
        
        # If choppiness increasing, spread likely widening
        if chop_second > chop_first * 1.2:
            trend = "WIDENING"
        elif chop_second < chop_first * 0.8:
            trend = "NARROWING"
        else:
            trend = "STABLE"
        
        return {'trend': trend, 'choppiness': choppiness}
    
    def _calculate_micro_alignment(self, prices: list) -> dict:
        """
        Calculate momentum alignment across micro timeframes (3s, 10s, 30s).
        
        Returns:
            {
                'alignment': {
                    '3s': "BULLISH" | "BEARISH" | "NEUTRAL",
                    '10s': "BULLISH" | "BEARISH" | "NEUTRAL",
                    '30s': "BULLISH" | "BEARISH" | "NEUTRAL"
                },
                'score': 0-100,
                'strength': "STRONG" | "MODERATE" | "WEAK" | "MISALIGNED"
            }
        """
        if len(prices) < 30:
            return {
                'alignment': {'3s': "NEUTRAL", '10s': "NEUTRAL", '30s': "NEUTRAL"},
                'score': 0,
                'strength': "UNKNOWN"
            }
        
        def get_direction(segment):
            if len(segment) < 2:
                return "NEUTRAL"
            momentum = self._calculate_micro_momentum(segment)
            if momentum > 0.05:
                return "BULLISH"
            elif momentum < -0.05:
                return "BEARISH"
            else:
                return "NEUTRAL"
        
        # 3s = last 3 ticks, 10s = last 10 ticks, 30s = all 30 ticks
        alignment = {
            '3s': get_direction(prices[-3:]),
            '10s': get_direction(prices[-10:]),
            '30s': get_direction(prices)
        }
        
        # Calculate alignment score
        directions = list(alignment.values())
        
        # Perfect alignment
        if all(d == "BULLISH" for d in directions):
            score = 100
            strength = "STRONG"
        elif all(d == "BEARISH" for d in directions):
            score = 100
            strength = "STRONG"
        # Partial alignment (2 out of 3)
        elif directions.count("BULLISH") == 2:
            score = 67
            strength = "MODERATE"
        elif directions.count("BEARISH") == 2:
            score = 67
            strength = "MODERATE"
        # Mixed or neutral
        elif "NEUTRAL" in directions:
            score = 33
            strength = "WEAK"
        else:
            score = 0
            strength = "MISALIGNED"
        
        return {
            'alignment': alignment,
            'score': score,
            'strength': strength
        }
    
    def _detect_key_level(self, prices: list) -> dict:
        """
        Detect support/resistance levels with touch counts.
        
        Returns:
            {
                'price': float,
                'touch_count': int,
                'type': "support" | "resistance",
                'last_touch_ago': int (seconds),
                'strength': "strong" | "weak"
            }
        """
        if len(prices) < 20:
            return None
        
        # Define price tolerance (0.1% of price)
        tolerance = prices[-1] * 0.001
        
        # Find local highs and lows
        levels = {}
        
        for i in range(2, len(prices) - 2):
            # Local high (resistance)
            if prices[i] > prices[i-1] and prices[i] > prices[i-2] and prices[i] > prices[i+1] and prices[i] > prices[i+2]:
                # Round to nearest level
                level = round(prices[i] / tolerance) * tolerance
                if level not in levels:
                    levels[level] = {'touches': [], 'type': 'resistance'}
                levels[level]['touches'].append(i)
            
            # Local low (support)
            elif prices[i] < prices[i-1] and prices[i] < prices[i-2] and prices[i] < prices[i+1] and prices[i] < prices[i+2]:
                level = round(prices[i] / tolerance) * tolerance
                if level not in levels:
                    levels[level] = {'touches': [], 'type': 'support'}
                levels[level]['touches'].append(i)
        
        if not levels:
            return None
        
        # Find level with most touches
        best_level = max(levels.items(), key=lambda x: len(x[1]['touches']))
        level_price = best_level[0]
        level_data = best_level[1]
        touch_count = len(level_data['touches'])
        
        if touch_count < 2:
            return None
        
        # Calculate seconds since last touch
        last_touch_idx = level_data['touches'][-1]
        last_touch_ago = len(prices) - last_touch_idx - 1
        
        return {
            'price': level_price,
            'touch_count': touch_count,
            'type': level_data['type'],
            'last_touch_ago': last_touch_ago,
            'strength': 'strong' if touch_count >= 3 else 'weak'
        }
    
    def _detect_momentum_divergence(self, prices: list, volumes: list) -> dict:
        """
        Detect divergence between price and volume momentum.
        
        Returns:
            {
                'type': "BULLISH" | "BEARISH" | "NONE",
                'strength': 0-100
            }
        """
        if len(prices) < 20 or len(volumes) < 20:
            return {'type': "NONE", 'strength': 0}
        
        # Split into two halves
        mid = len(prices) // 2
        
        # Price direction
        price_first = prices[:mid]
        price_second = prices[mid:]
        price_trend_first = price_first[-1] - price_first[0]
        price_trend_second = price_second[-1] - price_second[0]
        
        # Volume direction
        vol_first = np.mean(volumes[:mid])
        vol_second = np.mean(volumes[mid:])
        vol_trend = vol_second - vol_first
        
        # Bullish divergence: Price making lower lows but volume increasing
        if price_trend_second < price_trend_first < 0 and vol_trend > 0:
            strength = min(100, int(abs(vol_trend / vol_first) * 100)) if vol_first > 0 else 0
            return {'type': "BULLISH", 'strength': strength}
        
        # Bearish divergence: Price making higher highs but volume decreasing
        elif price_trend_second > price_trend_first > 0 and vol_trend < 0:
            strength = min(100, int(abs(vol_trend / vol_first) * 100)) if vol_first > 0 else 0
            return {'type': "BEARISH", 'strength': strength}
        
        else:
            return {'type': "NONE", 'strength': 0}
    
    def _calculate_realtime_atr(self, prices: list) -> dict:
        """
        Calculate real-time ATR from Binance ticks.
        
        Returns:
            {'atr': float}
        """
        if len(prices) < 14:
            return {'atr': 0.0}
        
        # Calculate true ranges for last 14 periods
        true_ranges = []
        for i in range(1, min(15, len(prices))):
            high_low = abs(prices[i] - prices[i-1])
            true_ranges.append(high_low)
        
        # ATR is average of true ranges
        atr = np.mean(true_ranges) if true_ranges else 0.0
        
        return {'atr': atr}
    
    def _calculate_bollinger_bands(self, prices: list) -> dict:
        """
        Calculate Bollinger Bands and price position.
        
        Returns:
            {
                'position': "UPPER_BAND" | "LOWER_BAND" | "MIDDLE" | "OUTSIDE_UPPER" | "OUTSIDE_LOWER",
                'width_pct': float,
                'squeeze': bool
            }
        """
        if len(prices) < 20:
            return {'position': "UNKNOWN", 'width_pct': 0, 'squeeze': False}
        
        # Use last 20 prices
        bb_prices = prices[-20:]
        
        # Calculate middle band (SMA)
        middle = np.mean(bb_prices)
        
        # Calculate standard deviation
        std = np.std(bb_prices)
        
        # Upper and lower bands (2 std devs)
        upper = middle + (2 * std)
        lower = middle - (2 * std)
        
        # Current price
        current = prices[-1]
        
        # Determine position
        if current > upper:
            position = "OUTSIDE_UPPER"
        elif current > middle + std:
            position = "UPPER_BAND"
        elif current < lower:
            position = "OUTSIDE_LOWER"
        elif current < middle - std:
            position = "LOWER_BAND"
        else:
            position = "MIDDLE"
        
        # Band width as % of price
        width_pct = ((upper - lower) / middle) * 100 if middle > 0 else 0
        
        # Squeeze if width < 0.3%
        squeeze = width_pct < 0.3
        
        return {
            'position': position,
            'width_pct': width_pct,
            'squeeze': squeeze
        }
    
    def _calculate_move_speed(self, prices: list) -> dict:
        """
        Calculate speed of price movement.
        
        Returns:
            {
                'speed': "PARABOLIC" | "FAST" | "NORMAL" | "SLOW",
                'percentile': 0-100,
                'warning': bool
            }
        """
        if len(prices) < 10:
            return {'speed': "UNKNOWN", 'percentile': 50, 'warning': False}
        
        # Calculate tick-by-tick price changes
        changes = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
        
        # Average change per tick
        avg_change = np.mean(changes)
        
        # Standard deviation
        std_change = np.std(changes) if len(changes) > 1 else 0
        
        # Recent speed (last 5 ticks)
        recent_changes = changes[-5:]
        recent_speed = np.mean(recent_changes)
        
        # Calculate percentile (recent vs historical)
        if std_change > 0:
            z_score = (recent_speed - avg_change) / std_change
            # Convert to percentile (rough approximation)
            percentile = min(100, max(0, int((z_score + 3) / 6 * 100)))
        else:
            percentile = 50
        
        # Classify speed
        if percentile > 95:
            speed = "PARABOLIC"
            warning = True
        elif percentile > 75:
            speed = "FAST"
            warning = False
        elif percentile > 25:
            speed = "NORMAL"
            warning = False
        else:
            speed = "SLOW"
            warning = False
        
        return {
            'speed': speed,
            'percentile': percentile,
            'warning': warning
        }
    
    def _calculate_momentum_volume_alignment(self, prices: list, volumes: list) -> dict:
        """
        Check if volume increases with momentum.
        
        Returns:
            {
                'score': 0-100,
                'quality': "STRONG" | "MODERATE" | "WEAK",
                'confirmed': bool
            }
        """
        if len(prices) < 10 or len(volumes) < 10:
            return {'score': 0, 'quality': "UNKNOWN", 'confirmed': False}
        
        # Calculate momentum for each tick
        momentum_increases = 0
        volume_increases = 0
        aligned_increases = 0
        
        for i in range(1, len(prices)):
            price_up = prices[i] > prices[i-1]
            volume_up = volumes[i] > volumes[i-1]
            
            if price_up:
                momentum_increases += 1
                if volume_up:
                    aligned_increases += 1
            
            if volume_up:
                volume_increases += 1
        
        # Calculate alignment score
        if momentum_increases > 0:
            score = int((aligned_increases / momentum_increases) * 100)
        else:
            score = 0
        
        # Quality label
        if score >= 75:
            quality = "STRONG"
            confirmed = True
        elif score >= 50:
            quality = "MODERATE"
            confirmed = True
        else:
            quality = "WEAK"
            confirmed = False
        
        return {
            'score': score,
            'quality': quality,
            'confirmed': confirmed
        }
    
    def _calculate_tick_frequency(self, history: list) -> dict:
        """
        Calculate tick frequency and activity level.
        
        Returns:
            {
                'ticks_per_sec': float,
                'activity_level': "VERY_HIGH" | "HIGH" | "NORMAL" | "LOW",
                'percentile': 0-100
            }
        """
        if len(history) < 10:
            return {'ticks_per_sec': 0.0, 'activity_level': "UNKNOWN", 'percentile': 50}
        
        # Calculate time span
        times = [t.get('timestamp', 0) for t in history]
        if not times or times[-1] == times[0]:
            return {'ticks_per_sec': 1.0, 'activity_level': "NORMAL", 'percentile': 50}
        
        time_span = (times[-1] - times[0]) / 1000  # Convert ms to seconds
        ticks_per_sec = len(history) / time_span if time_span > 0 else 1.0
        
        # Classify activity (assuming 1 tick/sec is normal)
        # Very high: >2 ticks/sec, High: >1.5, Normal: 0.8-1.5, Low: <0.8
        if ticks_per_sec > 2.0:
            activity = "VERY_HIGH"
            percentile = 90
        elif ticks_per_sec > 1.5:
            activity = "HIGH"
            percentile = 75
        elif ticks_per_sec > 0.8:
            activity = "NORMAL"
            percentile = 50
        else:
            activity = "LOW"
            percentile = 25
        
        return {
            'ticks_per_sec': round(ticks_per_sec, 2),
            'activity_level': activity,
            'percentile': percentile
        }
    
    def _calculate_price_zscore(self, prices: list) -> dict:
        """
        Calculate price Z-Score for mean reversion.
        
        Returns:
            {
                'zscore': float,
                'extremity': "EXTREME_HIGH" | "HIGH" | "NORMAL" | "LOW" | "EXTREME_LOW",
                'signal': "OVERBOUGHT" | "OVERSOLD" | "NEUTRAL"
            }
        """
        if len(prices) < 20:
            return {'zscore': 0.0, 'extremity': "UNKNOWN", 'signal': "NEUTRAL"}
        
        # Calculate mean and std dev
        mean = np.mean(prices)
        std = np.std(prices)
        
        if std == 0:
            return {'zscore': 0.0, 'extremity': "NORMAL", 'signal': "NEUTRAL"}
        
        # Current price Z-score
        current = prices[-1]
        zscore = (current - mean) / std
        
        # Classify extremity
        if zscore > 2.5:
            extremity = "EXTREME_HIGH"
            signal = "OVERBOUGHT"
        elif zscore > 1.5:
            extremity = "HIGH"
            signal = "OVERBOUGHT"
        elif zscore < -2.5:
            extremity = "EXTREME_LOW"
            signal = "OVERSOLD"
        elif zscore < -1.5:
            extremity = "LOW"
            signal = "OVERSOLD"
        else:
            extremity = "NORMAL"
            signal = "NEUTRAL"
        
        return {
            'zscore': round(zscore, 2),
            'extremity': extremity,
            'signal': signal
        }
    
    def _calculate_pivot_points(self, prices: list) -> dict:
        """
        Calculate intraday pivot points.
        
        Returns:
            {
                'pivot': float,
                'r1': float,
                'r2': float,
                's1': float,
                's2': float,
                'position': "ABOVE_R2" | "ABOVE_R1" | "ABOVE_PIVOT" | "BELOW_PIVOT" | "BELOW_S1" | "BELOW_S2"
            }
        """
        if len(prices) < 20:
            return {'pivot': 0, 'r1': 0, 'r2': 0, 's1': 0, 's2': 0, 'position': "UNKNOWN"}
        
        # Use last 20 ticks as "session"
        high = max(prices)
        low = min(prices)
        close = prices[-1]
        
        # Standard pivot point formula
        pivot = (high + low + close) / 3
        r1 = (2 * pivot) - low
        r2 = pivot + (high - low)
        s1 = (2 * pivot) - high
        s2 = pivot - (high - low)
        
        # Determine position
        current = prices[-1]
        if current > r2:
            position = "ABOVE_R2"
        elif current > r1:
            position = "ABOVE_R1"
        elif current > pivot:
            position = "ABOVE_PIVOT"
        elif current < s2:
            position = "BELOW_S2"
        elif current < s1:
            position = "BELOW_S1"
        else:
            position = "BELOW_PIVOT"
        
        return {
            'pivot': round(pivot, 2),
            'r1': round(r1, 2),
            'r2': round(r2, 2),
            's1': round(s1, 2),
            's2': round(s2, 2),
            'position': position
        }
    
    def _analyze_tape_reading(self, prices: list, volumes: list) -> dict:
        """
        Analyze tape for aggressor side (buyer vs seller initiated).
        
        Returns:
            {
                'aggressor': "BUYERS" | "SELLERS" | "BALANCED",
                'strength': 0-100,
                'dominance': "STRONG" | "MODERATE" | "WEAK"
            }
        """
        if len(prices) < 10 or len(volumes) < 10:
            return {'aggressor': "UNKNOWN", 'strength': 50, 'dominance': "UNKNOWN"}
        
        # Infer aggressor from price movement and volume
        # Up tick + high volume = buyer aggression
        # Down tick + high volume = seller aggression
        
        buyer_volume = 0
        seller_volume = 0
        
        for i in range(1, len(prices)):
            volume = volumes[i]
            if prices[i] > prices[i-1]:
                buyer_volume += volume
            elif prices[i] < prices[i-1]:
                seller_volume += volume
        
        total_volume = buyer_volume + seller_volume
        if total_volume == 0:
            return {'aggressor': "BALANCED", 'strength': 50, 'dominance': "WEAK"}
        
        # Calculate buyer dominance
        buyer_pct = (buyer_volume / total_volume) * 100
        
        if buyer_pct > 65:
            aggressor = "BUYERS"
            strength = int(buyer_pct)
            dominance = "STRONG" if buyer_pct > 75 else "MODERATE"
        elif buyer_pct < 35:
            aggressor = "SELLERS"
            strength = int(100 - buyer_pct)
            dominance = "STRONG" if buyer_pct < 25 else "MODERATE"
        else:
            aggressor = "BALANCED"
            strength = 50
            dominance = "WEAK"
        
        return {
            'aggressor': aggressor,
            'strength': strength,
            'dominance': dominance
        }
    
    def _calculate_liquidity_score(self, prices: list, volumes: list) -> dict:
        """
        Calculate liquidity score (proxy from volatility and volume).
        
        Returns:
            {
                'score': 0-100,
                'quality': "EXCELLENT" | "GOOD" | "FAIR" | "POOR",
                'exec_confidence': "HIGH" | "MEDIUM" | "LOW"
            }
        """
        if len(prices) < 10 or len(volumes) < 10:
            return {'score': 50, 'quality': "UNKNOWN", 'exec_confidence': "MEDIUM"}
        
        # High liquidity = low volatility + high volume
        # Calculate price stability (inverse of volatility)
        price_std = np.std(prices)
        price_range = max(prices) - min(prices)
        avg_price = np.mean(prices)
        
        # Volatility as % of price
        volatility_pct = (price_range / avg_price) * 100 if avg_price > 0 else 10
        
        # Stability score (lower volatility = higher score)
        # Assuming <0.5% volatility is excellent, >2% is poor
        if volatility_pct < 0.5:
            stability_score = 100
        elif volatility_pct < 1.0:
            stability_score = 80
        elif volatility_pct < 2.0:
            stability_score = 60
        else:
            stability_score = 40
        
        # Volume consistency
        avg_volume = np.mean(volumes)
        volume_std = np.std(volumes)
        volume_cv = (volume_std / avg_volume) if avg_volume > 0 else 1.0
        
        # Lower coefficient of variation = more consistent = better liquidity
        if volume_cv < 0.3:
            volume_score = 100
        elif volume_cv < 0.6:
            volume_score = 80
        elif volume_cv < 1.0:
            volume_score = 60
        else:
            volume_score = 40
        
        # Combined score
        score = int((stability_score + volume_score) / 2)
        
        # Quality label
        if score >= 85:
            quality = "EXCELLENT"
            exec_confidence = "HIGH"
        elif score >= 70:
            quality = "GOOD"
            exec_confidence = "HIGH"
        elif score >= 50:
            quality = "FAIR"
            exec_confidence = "MEDIUM"
        else:
            quality = "POOR"
            exec_confidence = "LOW"
        
        return {
            'score': score,
            'quality': quality,
            'exec_confidence': exec_confidence
        }
    
    def _get_time_of_day_context(self, symbol: str) -> dict:
        """
        Get time-of-day context for volatility expectations.
        
        Returns:
            {
                'hour': int,
                'session': "ASIAN" | "LONDON" | "NY" | "OFF_HOURS",
                'vol_comparison': "HIGHER" | "NORMAL" | "LOWER"
            }
        """
        from datetime import datetime
        
        now = datetime.utcnow()
        hour = now.hour
        
        # Determine session (UTC times)
        # Asian: 00:00-08:00, London: 08:00-16:00, NY: 13:00-21:00, Off: 21:00-00:00
        if 0 <= hour < 8:
            session = "ASIAN"
        elif 8 <= hour < 13:
            session = "LONDON"
        elif 13 <= hour < 21:
            session = "NY"
        else:
            session = "OFF_HOURS"
        
        # For simplicity, assume NY session has highest volatility
        # In production, this would reference historical data
        if session == "NY":
            vol_comparison = "HIGHER"
        elif session == "LONDON":
            vol_comparison = "NORMAL"
        elif session == "ASIAN":
            vol_comparison = "LOWER"
        else:
            vol_comparison = "LOWER"
        
        return {
            'hour': hour,
            'session': session,
            'vol_comparison': vol_comparison
        }
    
    def _detect_candle_pattern(self, prices: list, volumes: list) -> dict:
        """
        Detect classic candle patterns.
        
        Returns:
            {
                'pattern': "DOJI" | "HAMMER" | "SHOOTING_STAR" | "ENGULFING_BULL" | "ENGULFING_BEAR" | "NONE",
                'confidence': 0-100,
                'direction': "BULLISH" | "BEARISH" | "NEUTRAL"
            }
        """
        if len(prices) < 4:
            return {'pattern': "NONE", 'confidence': 0, 'direction': "NEUTRAL"}
        
        # Get last "candle" (last 4 ticks as OHLC)
        open_price = prices[-4]
        high = max(prices[-4:])
        low = min(prices[-4:])
        close = prices[-1]
        
        body = abs(close - open_price)
        range_size = high - low
        
        if range_size == 0:
            return {'pattern': "NONE", 'confidence': 0, 'direction': "NEUTRAL"}
        
        body_pct = (body / range_size) * 100
        
        # DOJI: Very small body (<10% of range)
        if body_pct < 10:
            return {'pattern': "DOJI", 'confidence': 80, 'direction': "NEUTRAL"}
        
        # HAMMER: Small body, long lower wick (bullish)
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        
        if lower_wick > body * 2 and upper_wick < body * 0.3 and close < open_price:
            return {'pattern': "HAMMER", 'confidence': 75, 'direction': "BULLISH"}
        
        # SHOOTING STAR: Small body, long upper wick (bearish)
        if upper_wick > body * 2 and lower_wick < body * 0.3 and close > open_price:
            return {'pattern': "SHOOTING_STAR", 'confidence': 75, 'direction': "BEARISH"}
        
        # ENGULFING: Compare to previous "candle"
        if len(prices) >= 8:
            prev_open = prices[-8]
            prev_close = prices[-5]
            prev_body = abs(prev_close - prev_open)
            
            # Bullish engulfing
            if close > open_price and prev_close < prev_open and body > prev_body * 1.5:
                return {'pattern': "ENGULFING_BULL", 'confidence': 85, 'direction': "BULLISH"}
            
            # Bearish engulfing
            if close < open_price and prev_close > prev_open and body > prev_body * 1.5:
                return {'pattern': "ENGULFING_BEAR", 'confidence': 85, 'direction': "BEARISH"}
        
        return {'pattern': "NONE", 'confidence': 0, 'direction': "NEUTRAL"}
        
    def get_binance_confirmation(
        self,
        symbol: str,
        mt5_signal: str,
        threshold: float = 0.5
    ) -> tuple[bool, str]:
        """
        Check if Binance microstructure confirms MT5 signal.
        
        Args:
            symbol: Trading symbol
            mt5_signal: "BUY" or "SELL" from MT5 analysis
            threshold: Minimum momentum required for confirmation (%)
            
        Returns:
            (confirmed, reason)
        """
        if not self.binance_service or not self.binance_service.running:
            return True, "Binance not available - using MT5 only"
            
        try:
            # Get recent price history
            history = self.binance_service.get_history(symbol, count=10)
            
            if len(history) < 10:
                return True, "Insufficient Binance data"
                
            prices = [t['price'] for t in history]
            momentum = self._calculate_micro_momentum(prices)
            
            if mt5_signal == "BUY":
                if momentum > threshold:
                    return True, f"Binance confirms BUY (momentum: +{momentum:.2f}%)"
                elif momentum < -threshold:
                    return False, f"Binance contradicts BUY (momentum: {momentum:.2f}%)"
                else:
                    return True, f"Binance neutral (momentum: {momentum:.2f}%)"
                    
            elif mt5_signal == "SELL":
                if momentum < -threshold:
                    return True, f"Binance confirms SELL (momentum: {momentum:.2f}%)"
                elif momentum > threshold:
                    return False, f"Binance contradicts SELL (momentum: +{momentum:.2f}%)"
                else:
                    return True, f"Binance neutral (momentum: {momentum:.2f}%)"
                    
            return True, "Unknown signal type"
            
        except Exception as e:
            logger.warning(f"Binance confirmation failed: {e}")
            return True, "Confirmation check failed - proceeding"
            
    def get_enrichment_summary(self, symbol: str) -> str:
        """
        Get a human-readable summary of Binance enrichment data.
        
        Returns:
            Multi-line summary string
        """
        if not self.binance_service or not self.binance_service.running:
            return "📡 Binance: Not available"
            
        try:
            tick = self.binance_service.get_latest_tick(symbol)
            if not tick:
                return "📡 Binance: No data"
                
            health = self.binance_service.get_feed_health(symbol)
            
            # Get recent history for advanced metrics
            history = self.binance_service.get_history(symbol, count=30)
            momentum = 0.0
            trend = "UNKNOWN"
            volatility = 0.0
            volume_surge = False
            momentum_accel = 0.0
            
            if len(history) >= 10:
                prices = [t['price'] for t in history]
                momentum = self._calculate_micro_momentum(prices)
                
                if len(history) >= 30:
                    trend = self._get_price_trend(prices[-10:])
                    volatility = self._calculate_volatility(prices)
                    momentum_accel = self._calculate_momentum_acceleration(prices)
                    
                    volumes = [t['volume'] for t in history]
                    volume_surge = self._detect_volume_surge(volumes)
                
            status_emoji = {
                "healthy": "✅",
                "warning": "⚠️",
                "critical": "🔴"
            }.get(health.get('overall_status', 'unknown'), "❓")
            
            trend_emoji = "📈" if trend == "RISING" else "📉" if trend == "FALLING" else "➡️"
            
            summary = (
                f"📡 Binance Feed:\n"
                f"  {status_emoji} Status: {health.get('overall_status', 'unknown').upper()}\n"
                f"  💰 Price: ${tick['price']:,.2f}\n"
                f"  {trend_emoji} Trend (10s): {trend}\n"
                f"  📈 Micro Momentum: {momentum:+.2f}%"
            )
            
            # Add momentum acceleration if significant
            if abs(momentum_accel) > 0.02:
                accel_emoji = "⚡" if momentum_accel > 0 else "🔻"
                summary += f" {accel_emoji}"
            
            summary += f"\n  📊 Volatility: {volatility:.3f}%"
            
            if volume_surge:
                summary += f"\n  🔥 Volume Surge Detected"
            
            # 🔥 NEW: Add Top 5 enrichment fields
            if len(history) >= 30:
                prices = [t['price'] for t in history]
                
                # 1. Price Structure
                structure_data = self._detect_price_structure(prices)
                structure = structure_data['structure']
                structure_emoji = {
                    "HIGHER_HIGH": "📈⬆️",
                    "HIGHER_LOW": "📈🔼",
                    "LOWER_HIGH": "📉🔽",
                    "LOWER_LOW": "📉⬇️",
                    "EQUAL": "➡️",
                    "CHOPPY": "🌀"
                }.get(structure, "❓")
                
                if structure not in ["UNKNOWN", "CHOPPY"]:
                    consecutive = structure_data['consecutive_count']
                    summary += f"\n\n🎯 Market Structure:\n"
                    summary += f"  {structure_emoji} {structure.replace('_', ' ')} ({consecutive}x)"
                
                # 2. Volatility State
                vol_state_data = self._detect_volatility_state(prices)
                vol_state = vol_state_data['state']
                if vol_state != "UNKNOWN":
                    vol_emoji = "💥" if vol_state == "EXPANDING" else "🔐" if vol_state == "CONTRACTING" else "⚖️"
                    vol_change = vol_state_data['change_pct']
                    summary += f"\n  {vol_emoji} Volatility: {vol_state} ({vol_change:+.1f}%)"
                    
                    if vol_state == "CONTRACTING" and vol_state_data.get('squeeze_duration', 0) > 20:
                        summary += f" 🔥 {vol_state_data['squeeze_duration']}s squeeze!"
                
                # 3. Momentum Quality
                mom_quality = self._calculate_momentum_consistency(prices)
                quality_label = mom_quality['quality_label']
                if quality_label != "UNKNOWN":
                    quality_emoji = "✅" if quality_label == "EXCELLENT" else "🟢" if quality_label == "GOOD" else "🟡" if quality_label == "FAIR" else "🔴"
                    summary += f"\n  {quality_emoji} Momentum: {quality_label} ({mom_quality['consistency_score']}%)"
                    if mom_quality['consecutive_moves'] >= 5:
                        summary += f" 🔥 {mom_quality['consecutive_moves']} consecutive!"
                
                # 4. Spread Proxy (Choppiness)
                spread_data = self._analyze_spread_proxy(prices)
                if spread_data['choppiness'] > 70:
                    summary += f"\n  🌀 High Choppiness: {spread_data['choppiness']}/100 (Spread: {spread_data['trend']})"
                elif spread_data['trend'] == "NARROWING":
                    summary += f"\n  ✅ Spread Narrowing (Good liquidity)"
                
                # 5. Micro Alignment
                alignment_data = self._calculate_micro_alignment(prices)
                if alignment_data['score'] >= 67:
                    strength = alignment_data['strength']
                    score = alignment_data['score']
                    alignment = alignment_data['alignment']
                    
                    summary += f"\n  🎯 Micro Alignment: {strength} ({score}%)"
                    summary += f"\n     3s:{alignment['3s'][0]} 10s:{alignment['10s'][0]} 30s:{alignment['30s'][0]}"
                
                # 🔥 PHASE 2A: Show key advanced signals
                volumes = [t['volume'] for t in history]
                
                # 6. Key Level (if detected)
                key_level = self._detect_key_level(prices)
                if key_level:
                    level_emoji = "🎯" if key_level['type'] == 'resistance' else "🛡️"
                    strength_emoji = "💪" if key_level['strength'] == 'strong' else "🤏"
                    summary += f"\n\n🔍 Key Level Detected:\n"
                    summary += f"  {level_emoji} {key_level['type'].title()}: ${key_level['price']:,.2f} "
                    summary += f"({key_level['touch_count']} touches {strength_emoji})"
                    if key_level['last_touch_ago'] < 5:
                        summary += f" 🔥 Fresh!"
                
                # 7. Momentum Divergence (if detected)
                divergence = self._detect_momentum_divergence(prices, volumes)
                if divergence['type'] != "NONE":
                    div_emoji = "🟢⬆️" if divergence['type'] == "BULLISH" else "🔴⬇️"
                    summary += f"\n  {div_emoji} {divergence['type']} Divergence ({divergence['strength']}%)"
                
                # 8. Real-Time ATR comparison
                rt_atr = self._calculate_realtime_atr(prices)
                # Will show ATR divergence in main analysis if MT5 data available
                
                # 9. Bollinger Bands (if extreme)
                bb_data = self._calculate_bollinger_bands(prices)
                if bb_data['position'] in ["OUTSIDE_UPPER", "OUTSIDE_LOWER"]:
                    bb_emoji = "🔴" if bb_data['position'] == "OUTSIDE_UPPER" else "🟢"
                    summary += f"\n  {bb_emoji} Bollinger: {bb_data['position'].replace('_', ' ')}"
                elif bb_data['squeeze']:
                    summary += f"\n  🔐 Bollinger Squeeze ({bb_data['width_pct']:.2f}% width) 🔥"
                
                # 10. Speed Warning (if parabolic)
                speed_data = self._calculate_move_speed(prices)
                if speed_data['warning']:
                    summary += f"\n  ⚠️ PARABOLIC Move ({speed_data['percentile']}th percentile) - Don't chase!"
                elif speed_data['speed'] == "FAST":
                    summary += f"\n  🚀 Fast Move ({speed_data['percentile']}th percentile)"
                
                # 11. Volume Confirmation
                mv_alignment = self._calculate_momentum_volume_alignment(prices, volumes)
                if mv_alignment['quality'] in ["STRONG", "WEAK"]:
                    mv_emoji = "✅" if mv_alignment['quality'] == "STRONG" else "⚠️"
                    summary += f"\n  {mv_emoji} Volume Confirmation: {mv_alignment['quality']} ({mv_alignment['score']}%)"
                
                # 🔥 PHASE 2B: Show advanced enrichments
                
                # 12. Tick Frequency (if unusual)
                tick_freq = self._calculate_tick_frequency(history)
                if tick_freq['activity_level'] in ["VERY_HIGH", "LOW"]:
                    freq_emoji = "🔥" if tick_freq['activity_level'] == "VERY_HIGH" else "🐌"
                    summary += f"\n  {freq_emoji} Activity: {tick_freq['activity_level']} ({tick_freq['ticks_per_sec']}/s)"
                
                # 13. Price Z-Score (if extreme)
                z_score_data = self._calculate_price_zscore(prices)
                if z_score_data['signal'] != "NEUTRAL":
                    zscore_emoji = "🔴" if z_score_data['signal'] == "OVERBOUGHT" else "🟢"
                    summary += f"\n  {zscore_emoji} Z-Score: {z_score_data['extremity']} ({z_score_data['zscore']}σ) - {z_score_data['signal']}"
                
                # 14. Pivot Points (if near extremes)
                pivots = self._calculate_pivot_points(prices)
                if pivots['position'] in ["ABOVE_R2", "BELOW_S2"]:
                    pivot_emoji = "🎯"
                    summary += f"\n  {pivot_emoji} Pivot: {pivots['position'].replace('_', ' ')}"
                    if pivots['position'] == "ABOVE_R2":
                        summary += f" (Resistance 2: ${pivots['r2']:,.2f})"
                    else:
                        summary += f" (Support 2: ${pivots['s2']:,.2f})"
                
                # 15. Tape Reading (if strong dominance)
                tape_data = self._analyze_tape_reading(prices, volumes)
                if tape_data['dominance'] == "STRONG":
                    tape_emoji = "🟢💪" if tape_data['aggressor'] == "BUYERS" else "🔴💪"
                    summary += f"\n  {tape_emoji} Tape: {tape_data['aggressor']} DOMINATING ({tape_data['strength']}%)"
                
                # 16. Liquidity Score (if poor)
                liquidity_score = self._calculate_liquidity_score(prices, volumes)
                if liquidity_score['quality'] in ["EXCELLENT", "POOR"]:
                    liq_emoji = "✅" if liquidity_score['quality'] == "EXCELLENT" else "⚠️"
                    summary += f"\n  {liq_emoji} Liquidity: {liquidity_score['quality']} ({liquidity_score['score']}/100) - Execution: {liquidity_score['exec_confidence']}"
                
                # 17. Time-of-Day Context (show session)
                tod_context = self._get_time_of_day_context(symbol)
                session_emoji = {
                    "ASIAN": "🌏",
                    "LONDON": "🇬🇧",
                    "NY": "🇺🇸",
                    "OFF_HOURS": "🌙"
                }.get(tod_context['session'], "⏰")
                summary += f"\n  {session_emoji} Session: {tod_context['session']} ({tod_context['hour']:02d}:00 UTC)"
                
                # 18. Candle Pattern (if detected)
                pattern = self._detect_candle_pattern(prices, volumes)
                if pattern['pattern'] != "NONE":
                    pattern_emoji = "🟢" if pattern['direction'] == "BULLISH" else "🔴" if pattern['direction'] == "BEARISH" else "⚪"
                    summary += f"\n  {pattern_emoji} Pattern: {pattern['pattern'].replace('_', ' ')} ({pattern['confidence']}% confidence)"
            
            summary += f"\n\n  ⏱️ Age: {health.get('cache', {}).get('age_seconds', 0):.1f}s"
            summary += f"\n  🔄 Offset: {health.get('sync', {}).get('offset', 'N/A')}"
            
            if isinstance(health.get('sync', {}).get('offset'), (int, float)):
                summary += f" pips"
            
            # Add order flow if available
            if self.order_flow_service and self.order_flow_service.running:
                try:
                    order_flow = self.order_flow_service.get_order_flow_signal(symbol)
                    if order_flow:
                        signal_emoji = "🟢" if order_flow['signal'] == "BULLISH" else "🔴" if order_flow['signal'] == "BEARISH" else "⚪"
                        imbalance = order_flow.get('order_book', {}).get('imbalance')
                        whale_count = order_flow.get('whale_activity', {}).get('total_whales', 0)
                        voids = len(order_flow.get('liquidity_voids', []))
                        
                        summary += (
                            f"\n\n📊 Order Flow:\n"
                            f"  {signal_emoji} Signal: {order_flow['signal']} ({order_flow['confidence']:.0f}%)\n"
                        )
                        
                        if imbalance:
                            imb_emoji = "🟢" if imbalance > 1.2 else "🔴" if imbalance < 0.8 else "⚪"
                            summary += f"  {imb_emoji} Book Imbalance: {imbalance:.2f}\n"
                        
                        if whale_count > 0:
                            summary += f"  🐋 Whale Orders (60s): {whale_count}\n"
                        
                        if voids > 0:
                            summary += f"  ⚠️ Liquidity Voids: {voids}\n"
                        
                        if order_flow.get('warnings'):
                            summary += f"  ⚠️ {order_flow['warnings'][0]}"
                except Exception as e:
                    logger.debug(f"Could not add order flow to summary: {e}")
                
            return summary
            
        except Exception as e:
            return f"📡 Binance: Error - {e}"


# Example usage
def example_usage():
    """
    Example of how to use BinanceEnrichment.
    """
    from infra.binance_service import BinanceService
    from infra.mt5_service import MT5Service
    
    # Initialize services
    mt5 = MT5Service()
    mt5.connect()
    
    binance = BinanceService()
    # binance.start(["btcusdt"]) would be called elsewhere
    
    # Create enricher
    enricher = BinanceEnrichment(binance, mt5)
    
    # Mock MT5 data
    mt5_m5 = {
        "close": 112150.0,
        "atr_14": 450.0,
        "ema_200": 111800.0,
        "adx_14": 28.5
    }
    
    # Enrich with Binance data
    enriched = enricher.enrich_timeframe("BTCUSDc", mt5_m5, "M5")
    
    print("Original MT5 data:", mt5_m5)
    print("\nEnriched data:", enriched)
    
    # Check confirmation
    confirmed, reason = enricher.get_binance_confirmation("BTCUSDc", "BUY")
    print(f"\nBUY signal confirmed: {confirmed}")
    print(f"Reason: {reason}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    example_usage()

