# =====================================
# infra/m1_microstructure_analyzer.py
# =====================================
"""
M1 Microstructure Analyzer

Analyzes M1 candlestick data to extract microstructure patterns:
- CHOCH/BOS detection
- Liquidity zones (PDH/PDL, equal highs/lows)
- Volatility state (CONTRACTING/EXPANDING/STABLE)
- Rejection wicks and order blocks
- Momentum quality and trend context
- Microstructure confluence scoring
"""

from __future__ import annotations

import logging
import statistics
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# LogContext for per-symbol tracing
log_context: ContextVar[Dict[str, str]] = ContextVar('log_context', default={})


class M1MicrostructureAnalyzer:
    """
    Analyzes M1 candlestick data to extract microstructure patterns.
    
    Supports optional integrations:
    - session_manager: SessionVolatilityProfile for session-aware analysis
    - asset_profiles: AssetProfile for asset-specific behavior
    - strategy_selector: StrategySelector for strategy hint generation
    - signal_learner: RealTimeSignalLearner for adaptive calibration
    - threshold_manager: SymbolThresholdManager for dynamic threshold tuning
    """
    
    def __init__(
        self,
        mt5_service=None,
        session_manager=None,
        asset_profiles=None,
        strategy_selector=None,
        signal_learner=None,
        threshold_manager=None
    ):
        """
        Initialize M1 Microstructure Analyzer.
        
        Args:
            mt5_service: MT5Service for higher timeframe data (optional)
            session_manager: SessionVolatilityProfile (optional, for Phase 2.6)
            asset_profiles: AssetProfile (optional, for Phase 2.6)
            strategy_selector: StrategySelector (optional, for Phase 2.6)
            signal_learner: RealTimeSignalLearner (optional, for Phase 2.6)
            threshold_manager: SymbolThresholdManager (optional, for Dynamic Threshold Tuning)
        """
        self.mt5_service = mt5_service
        self.session_manager = session_manager
        self.asset_profiles = asset_profiles
        self.strategy_selector = strategy_selector
        self.signal_learner = signal_learner
        self.threshold_manager = threshold_manager
        
        self.logger = logging.getLogger(__name__)
        
        # Track last signal timestamp per symbol
        self._last_signal_timestamp: Dict[str, str] = {}
        
        # Cache for microstructure analysis results (Phase 4.2)
        self._analysis_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl = 300  # 5 minutes TTL (configurable)
        self._cache_max_size = 100  # Maximum number of cached results
        
        logger.info("M1MicrostructureAnalyzer initialized")
    
    def _log_with_context(self, level: str, message: str, symbol: str = None):
        """Log with per-symbol context for easier debugging and monitoring."""
        context = log_context.get()
        if symbol:
            context = {**context, 'symbol': symbol}
        
        log_msg = f"[{context.get('symbol', 'UNKNOWN')}] {message}"
        
        if level == 'debug':
            self.logger.debug(log_msg, extra={'symbol': symbol, **context})
        elif level == 'info':
            self.logger.info(log_msg, extra={'symbol': symbol, **context})
        elif level == 'warning':
            self.logger.warning(log_msg, extra={'symbol': symbol, **context})
        elif level == 'error':
            self.logger.error(log_msg, extra={'symbol': symbol, **context})
    
    def analyze_microstructure(
        self,
        symbol: str,
        candles: List[Dict[str, Any]],
        current_price: Optional[float] = None,
        higher_timeframe_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Complete M1 microstructure analysis.
        
        Args:
            symbol: Symbol name
            candles: List of M1 candle dicts (oldest first)
            current_price: Current price (if None, uses last candle close)
            higher_timeframe_data: Optional dict with M5/H1 data for trend context
            
        Returns:
            Complete analysis dict with all microstructure insights
        """
        if not candles or len(candles) < 10:
            self._log_with_context('warning', f"Insufficient candles for analysis: {len(candles) if candles else 0}", symbol)
            return {
                'available': False,
                'error': 'Insufficient candles'
            }
        
        # Normalize symbol (remove 'c' suffix if present for internal use)
        normalized_symbol = symbol.rstrip('c') if symbol.endswith('c') else symbol
        
        # Check cache (Phase 4.2: Cache microstructure analysis results)
        cache_key = self._get_cache_key(normalized_symbol, candles)
        if cache_key:
            cached_result = self._get_cached_result(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {normalized_symbol} (key: {cache_key})")
                return cached_result
        
        # Get current price
        if current_price is None:
            current_price = candles[-1].get('close', 0)
        
        # Initialize analysis dict
        analysis = {
            'available': True,
            'symbol': normalized_symbol,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'candle_count': len(candles)
        }
        
        # 1. Structure Analysis
        analysis['structure'] = self.analyze_structure(candles, normalized_symbol)
        
        # 2. CHOCH/BOS Detection
        analysis['choch_bos'] = self.detect_choch_bos(candles, require_confirmation=True, symbol=normalized_symbol)
        
        # 3. Liquidity Zones
        analysis['liquidity_zones'] = self.identify_liquidity_zones(candles, normalized_symbol)
        
        # 4. Liquidity State
        analysis['liquidity_state'] = self.calculate_liquidity_state(candles, current_price, normalized_symbol)
        
        # 5. Volatility State
        analysis['volatility'] = self.calculate_volatility_state(candles, normalized_symbol)
        
        # 6. Rejection Wicks
        analysis['rejection_wicks'] = self.detect_rejection_wicks(candles, normalized_symbol)
        
        # 7. Order Blocks
        analysis['order_blocks'] = self.find_order_blocks(candles, normalized_symbol)
        
        # 8. Momentum Quality
        analysis['momentum'] = self.calculate_momentum_quality(candles, include_rsi=True, symbol=normalized_symbol)
        
        # 9. Trend Context (if higher timeframe data provided)
        if higher_timeframe_data:
            analysis['trend_context'] = self.trend_context(
                candles,
                higher_timeframe_data,
                include_m15=False,
                symbol=normalized_symbol
            )
        else:
            analysis['trend_context'] = {
                'alignment': 'UNKNOWN',
                'confidence': 0,
                'm1_m5_alignment': False,
                'm1_h1_alignment': False
            }
        
        # 10. Signal Summary
        analysis['signal_summary'] = self.generate_signal_summary(analysis, normalized_symbol)
        
        # 11. Signal Timestamp and Age
        if analysis['signal_summary'] != 'NEUTRAL':
            signal_ts = datetime.now(timezone.utc).isoformat()
            analysis['last_signal_timestamp'] = signal_ts
            analysis['signal_detection_timestamp'] = signal_ts
            self._last_signal_timestamp[normalized_symbol] = signal_ts
        else:
            # Use last known signal timestamp
            last_ts = self._last_signal_timestamp.get(normalized_symbol)
            if last_ts:
                analysis['last_signal_timestamp'] = last_ts
                analysis['signal_detection_timestamp'] = last_ts
            else:
                analysis['last_signal_timestamp'] = None
                analysis['signal_detection_timestamp'] = None
        
        analysis['signal_age_seconds'] = self.calculate_signal_age(analysis.get('last_signal_timestamp'))
        
        # 12. Session Context (if session_manager available)
        if self.session_manager:
            try:
                session_context = self.session_manager.get_session_context(symbol=normalized_symbol)
                analysis['session_context'] = {
                    'session': session_context.get('session', 'UNKNOWN'),
                    'volatility_tier': session_context.get('volatility_tier', 'NORMAL'),
                    'liquidity_timing': session_context.get('liquidity_timing', 'MODERATE'),
                    'typical_behavior': session_context.get('typical_behavior', ''),
                    'best_strategy_type': session_context.get('best_strategy_type', 'TREND_CONTINUATION'),
                    'session_bias_factor': session_context.get('session_bias_factor', 1.0),
                    'atr_multiplier_adjustment': session_context.get('atr_multiplier_adjustment', 1.0),
                    'vwap_stretch_tolerance': session_context.get('vwap_stretch_tolerance', 1.0),
                    'is_good_time_to_trade': session_context.get('is_good_time_to_trade', True),
                }
                analysis['session_adjusted_parameters'] = {
                    'atr_multiplier': session_context.get('atr_multiplier_adjustment', 1.0),
                    'vwap_stretch': session_context.get('vwap_stretch_tolerance', 1.0),
                    'bias_factor': session_context.get('session_bias_factor', 1.0),
                }
            except Exception as e:
                self._log_with_context('warning', f"Session context error: {e}", normalized_symbol)
                analysis['session_context'] = {'session': 'UNKNOWN'}
                analysis['session_adjusted_parameters'] = {}
        else:
            analysis['session_context'] = {'session': 'UNKNOWN'}
            analysis['session_adjusted_parameters'] = {}
        
        # 13. Asset Personality (if asset_profiles available)
        if self.asset_profiles:
            try:
                profile = self.asset_profiles.get_asset_profile(normalized_symbol)
                analysis['asset_personality'] = profile
                is_valid = self.asset_profiles.is_signal_valid_for_asset(normalized_symbol, analysis)
                analysis['signal_valid_for_asset'] = is_valid
            except Exception as e:
                self._log_with_context('warning', f"Asset profile error: {e}", normalized_symbol)
                analysis['asset_personality'] = None
                analysis['signal_valid_for_asset'] = True  # Default to valid if error
        else:
            analysis['asset_personality'] = None
            analysis['signal_valid_for_asset'] = True  # Default to valid if no profiles
        
        # 14. Strategy Hint (if strategy_selector available, otherwise generate manually)
        if self.strategy_selector:
            try:
                volatility_state = analysis.get('volatility', {}).get('state', 'STABLE')
                structure_alignment = self._get_structure_alignment(analysis.get('structure', {}))
                momentum_divergent = analysis.get('momentum', {}).get('quality') == 'CHOPPY'
                vwap_state = self._get_vwap_state(normalized_symbol, candles)
                
                strategy_hint = self.strategy_selector.choose(
                    volatility_state=volatility_state,
                    structure_alignment=structure_alignment,
                    momentum_divergent=momentum_divergent,
                    vwap_state=vwap_state
                )
                analysis['strategy_hint'] = strategy_hint
            except Exception as e:
                self._log_with_context('warning', f"Strategy selector error: {e}", normalized_symbol)
                analysis['strategy_hint'] = self.generate_strategy_hint(analysis)
        
        # 14.5. Add VWAP data to analysis (required by auto-execution system)
        try:
            vwap_value = self._calculate_vwap(candles)
            if vwap_value > 0:
                # Calculate VWAP standard deviation
                vwap_deviations = []
                for candle in candles:
                    typical_price = (candle.get('high', 0) + candle.get('low', 0) + candle.get('close', 0)) / 3
                    if typical_price > 0:
                        deviation = abs(typical_price - vwap_value)
                        vwap_deviations.append(deviation)
                
                vwap_std = statistics.stdev(vwap_deviations) if len(vwap_deviations) > 1 else 0.0
                
                analysis['vwap'] = {
                    'value': vwap_value,
                    'std': vwap_std,
                    'state': self._get_vwap_state(normalized_symbol, candles)
                }
            else:
                analysis['vwap'] = {
                    'value': None,
                    'std': 0.0,
                    'state': 'NEUTRAL'
                }
        except Exception as e:
            self._log_with_context('warning', f"VWAP calculation error: {e}", normalized_symbol)
            analysis['vwap'] = {
                'value': None,
                'std': 0.0,
                'state': 'NEUTRAL'
            }
        else:
            analysis['strategy_hint'] = self.generate_strategy_hint(analysis)
        
        # 15. Microstructure Confluence
        session = analysis.get('session_context', {}).get('session', 'UNKNOWN')
        analysis['microstructure_confluence'] = self.calculate_microstructure_confluence(
            analysis,
            session=session,
            symbol=normalized_symbol
        )
        
        # 16. Dynamic Threshold (if threshold_manager available)
        if self.threshold_manager:
            try:
                atr_current = analysis.get('volatility', {}).get('atr', 0)
                atr_median = analysis.get('volatility', {}).get('atr_median', atr_current)
                atr_ratio = atr_current / atr_median if atr_median > 0 else 1.0
                
                session = self.session_manager.get_current_session() if self.session_manager else "LONDON"
                
                dynamic_threshold = self.threshold_manager.compute_threshold(
                    symbol=normalized_symbol,
                    session=session,
                    atr_ratio=atr_ratio
                )
                
                analysis['dynamic_threshold'] = dynamic_threshold
                analysis['threshold_calculation'] = {
                    'base_confidence': self.threshold_manager.get_base_confidence(normalized_symbol),
                    'atr_ratio': atr_ratio,
                    'session_bias': self.threshold_manager.get_session_bias(session, normalized_symbol),
                    'adjusted_threshold': dynamic_threshold,
                    'session': session
                }
            except Exception as e:
                self._log_with_context('warning', f"Dynamic threshold error: {e}", normalized_symbol)
                analysis['dynamic_threshold'] = None
        else:
            analysis['dynamic_threshold'] = None
        
        # 17. Real-Time Signal Learning (Phase 2.2) - Get optimal parameters if available
        if self.signal_learner:
            try:
                session = analysis.get('session_context', {}).get('session', 'UNKNOWN')
                optimal_params = self.signal_learner.get_optimal_parameters(
                    symbol=normalized_symbol,
                    session=session,
                    min_samples=10
                )
                if optimal_params:
                    analysis['learning_metrics'] = optimal_params
                    self._log_with_context('debug', 
                        f"Learning metrics: threshold={optimal_params.get('optimal_confluence_threshold')}, "
                        f"win_rate={optimal_params.get('win_rate', 0):.1%}",
                        normalized_symbol)
            except Exception as e:
                self._log_with_context('warning', f"Signal learner error: {e}", normalized_symbol)
                analysis['learning_metrics'] = None
        else:
            analysis['learning_metrics'] = None
        
        # 18. Effective Confidence (confluence score adjusted by dynamic threshold context)
        base_score = analysis.get('microstructure_confluence', {}).get('base_score', 0)
        if analysis.get('dynamic_threshold'):
            # Effective confidence shows how much above/below threshold
            effective = base_score - analysis['dynamic_threshold']
            analysis['effective_confidence'] = base_score + (effective * 0.1)  # Slight boost if above threshold
        else:
            analysis['effective_confidence'] = base_score
        
        # Cache result (Phase 4.2: Cache microstructure analysis results)
        if cache_key:
            self._cache_result(cache_key, analysis)
        
        return analysis
    
    def analyze_structure(self, candles: List[Dict], symbol: str = None) -> Dict[str, Any]:
        """
        Analyze market structure (higher highs, lower lows, choppy).
        
        Args:
            candles: List of candle dicts
            symbol: Symbol name for logging
            
        Returns:
            Structure analysis dict
        """
        try:
            if len(candles) < 10:
                return {'type': 'UNKNOWN', 'consecutive_count': 0, 'strength': 0}
            
            # Find swing points (local highs and lows)
            swing_highs = []
            swing_lows = []
            
            for i in range(2, len(candles) - 2):
                high = candles[i].get('high', 0)
                low = candles[i].get('low', 0)
                
                # Check for swing high
                if (high > candles[i-1].get('high', 0) and
                    high > candles[i-2].get('high', 0) and
                    high > candles[i+1].get('high', 0) and
                    high > candles[i+2].get('high', 0)):
                    swing_highs.append({'price': high, 'index': i})
                
                # Check for swing low
                if (low < candles[i-1].get('low', 0) and
                    low < candles[i-2].get('low', 0) and
                    low < candles[i+1].get('low', 0) and
                    low < candles[i+2].get('low', 0)):
                    swing_lows.append({'price': low, 'index': i})
            
            if len(swing_highs) < 2 or len(swing_lows) < 2:
                return {'type': 'CHOPPY', 'consecutive_count': 0, 'strength': 30}
            
            # Analyze structure
            recent_highs = swing_highs[-3:]
            recent_lows = swing_lows[-3:]
            
            # Check for higher highs
            hh_count = 0
            for i in range(1, len(recent_highs)):
                if recent_highs[i]['price'] > recent_highs[i-1]['price']:
                    hh_count += 1
            
            # Check for lower lows
            ll_count = 0
            for i in range(1, len(recent_lows)):
                if recent_lows[i]['price'] < recent_lows[i-1]['price']:
                    ll_count += 1
            
            # Determine structure type
            if hh_count >= 2 and ll_count == 0:
                structure_type = 'HIGHER_HIGH'
                strength = min(100, 60 + (hh_count * 10))
            elif ll_count >= 2 and hh_count == 0:
                structure_type = 'LOWER_LOW'
                strength = min(100, 60 + (ll_count * 10))
            elif abs(hh_count - ll_count) <= 1:
                structure_type = 'CHOPPY'
                strength = 30
            else:
                structure_type = 'EQUAL'
                strength = 50
            
            return {
                'type': structure_type,
                'consecutive_count': max(hh_count, ll_count),
                'strength': strength
            }
            
        except Exception as e:
            self._log_with_context('error', f"Structure analysis error: {e}", symbol)
            return {'type': 'UNKNOWN', 'consecutive_count': 0, 'strength': 0}
    
    def detect_choch_bos(
        self,
        candles: List[Dict],
        require_confirmation: bool = True,
        symbol: str = None
    ) -> Dict[str, Any]:
        """
        Detect CHOCH (Change of Character) and BOS (Break of Structure).
        
        Uses 3-candle confirmation rule to reduce false positives.
        
        Args:
            candles: List of candle dicts
            require_confirmation: Use 3-candle confirmation (default: True)
            symbol: Symbol name for logging
            
        Returns:
            CHOCH/BOS detection dict
        """
        try:
            if len(candles) < 10:
                return {
                    'has_choch': False,
                    'has_bos': False,
                    'choch_confirmed': False,
                    'choch_bos_combo': False,
                    'last_swing_high': 0,
                    'last_swing_low': 0,
                    'confidence': 0
                }
            
            # Calculate ATR for normalization
            atr = self._calculate_atr(candles, period=14)
            if atr <= 0:
                atr = 1.0
            
            # Find swing points
            swing_highs = []
            swing_lows = []
            
            for i in range(2, len(candles) - 2):
                high = candles[i].get('high', 0)
                low = candles[i].get('low', 0)
                
                # Swing high
                if (high > candles[i-1].get('high', 0) and
                    high > candles[i-2].get('high', 0) and
                    high > candles[i+1].get('high', 0) and
                    high > candles[i+2].get('high', 0)):
                    swing_highs.append({'price': high, 'index': i})
                
                # Swing low
                if (low < candles[i-1].get('low', 0) and
                    low < candles[i-2].get('low', 0) and
                    low < candles[i+1].get('low', 0) and
                    low < candles[i+2].get('low', 0)):
                    swing_lows.append({'price': low, 'index': i})
            
            if not swing_highs or not swing_lows:
                return {
                    'has_choch': False,
                    'has_bos': False,
                    'choch_confirmed': False,
                    'choch_bos_combo': False,
                    'last_swing_high': candles[-1].get('high', 0),
                    'last_swing_low': candles[-1].get('low', 0),
                    'confidence': 0
                }
            
            last_swing_high = max(swing_highs, key=lambda x: x['price'])
            last_swing_low = min(swing_lows, key=lambda x: x['price'])
            
            current_close = candles[-1].get('close', 0)
            bos_threshold = 0.2 * atr  # 0.2 ATR minimum break
            
            # Check for bullish BOS
            has_bos_bull = False
            has_choch_bull = False
            
            if current_close > last_swing_high['price'] + bos_threshold:
                has_bos_bull = True
                
                # Check for CHOCH (reversal of structure)
                if len(swing_highs) >= 2:
                    prev_high = swing_highs[-2]['price']
                    if last_swing_high['price'] < prev_high:  # Was making lower highs
                        has_choch_bull = True
            
            # Check for bearish BOS
            has_bos_bear = False
            has_choch_bear = False
            
            if current_close < last_swing_low['price'] - bos_threshold:
                has_bos_bear = True
                
                # Check for CHOCH (reversal of structure)
                if len(swing_lows) >= 2:
                    prev_low = swing_lows[-2]['price']
                    if last_swing_low['price'] > prev_low:  # Was making higher lows
                        has_choch_bear = True
            
            has_bos = has_bos_bull or has_bos_bear
            has_choch = has_choch_bull or has_choch_bear
            choch_bos_combo = has_choch and has_bos
            
            # 3-candle confirmation
            choch_confirmed = False
            if require_confirmation and has_choch:
                if len(candles) >= 3:
                    # Check if last 3 candles confirm the break
                    recent_closes = [c.get('close', 0) for c in candles[-3:]]
                    if has_choch_bull:
                        # Bullish: all 3 closes should be above swing high
                        choch_confirmed = all(c > last_swing_high['price'] for c in recent_closes)
                    elif has_choch_bear:
                        # Bearish: all 3 closes should be below swing low
                        choch_confirmed = all(c < last_swing_low['price'] for c in recent_closes)
            elif has_choch:
                choch_confirmed = True  # No confirmation required
            
            # Calculate confidence
            confidence = 0
            if choch_bos_combo:
                confidence = 90
            elif has_choch and choch_confirmed:
                confidence = 85
            elif has_bos:
                confidence = 70
            elif has_choch:
                confidence = 60
            
            return {
                'has_choch': has_choch,
                'has_bos': has_bos,
                'choch_confirmed': choch_confirmed,
                'choch_bos_combo': choch_bos_combo,
                'last_swing_high': last_swing_high['price'],
                'last_swing_low': last_swing_low['price'],
                'confidence': confidence
            }
            
        except Exception as e:
            self._log_with_context('error', f"CHOCH/BOS detection error: {e}", symbol)
            return {
                'has_choch': False,
                'has_bos': False,
                'choch_confirmed': False,
                'choch_bos_combo': False,
                'last_swing_high': 0,
                'last_swing_low': 0,
                'confidence': 0
            }
    
    def identify_liquidity_zones(self, candles: List[Dict], symbol: str = None) -> List[Dict[str, Any]]:
        """
        Identify liquidity zones (PDH/PDL, equal highs/lows).
        
        Args:
            candles: List of candle dicts
            symbol: Symbol name for logging
            
        Returns:
            List of liquidity zone dicts
        """
        try:
            if len(candles) < 20:
                return []
            
            zones = []
            
            # Previous Day High/Low (last 24 hours = 1440 M1 candles, but use last 200 if available)
            lookback = min(200, len(candles))
            recent = candles[-lookback:]
            
            pdh = max(c.get('high', 0) for c in recent)
            pdl = min(c.get('low', 0) for c in recent)
            
            # Count touches
            pdh_touches = sum(1 for c in recent if abs(c.get('high', 0) - pdh) < (pdh * 0.001))
            pdl_touches = sum(1 for c in recent if abs(c.get('low', 0) - pdl) < (pdl * 0.001))
            
            if pdh_touches >= 2:
                zones.append({'type': 'PDH', 'price': pdh, 'touches': pdh_touches})
            
            if pdl_touches >= 2:
                zones.append({'type': 'PDL', 'price': pdl, 'touches': pdl_touches})
            
            # Equal highs/lows (swing points within tolerance)
            swing_highs = []
            swing_lows = []
            
            for i in range(2, len(candles) - 2):
                high = candles[i].get('high', 0)
                low = candles[i].get('low', 0)
                
                if (high > candles[i-1].get('high', 0) and
                    high > candles[i-2].get('high', 0) and
                    high > candles[i+1].get('high', 0) and
                    high > candles[i+2].get('high', 0)):
                    swing_highs.append(high)
                
                if (low < candles[i-1].get('low', 0) and
                    low < candles[i-2].get('low', 0) and
                    low < candles[i+1].get('low', 0) and
                    low < candles[i+2].get('low', 0)):
                    swing_lows.append(low)
            
            # Find equal highs (within 0.1% tolerance)
            if len(swing_highs) >= 2:
                tolerance = statistics.mean(swing_highs) * 0.001
                equal_highs = self._find_equal_levels(swing_highs, tolerance)
                for level, touches in equal_highs.items():
                    if touches >= 2:
                        zones.append({'type': 'EQUAL_HIGH', 'price': level, 'touches': touches})
            
            # Find equal lows (within 0.1% tolerance)
            if len(swing_lows) >= 2:
                tolerance = statistics.mean(swing_lows) * 0.001
                equal_lows = self._find_equal_levels(swing_lows, tolerance)
                for level, touches in equal_lows.items():
                    if touches >= 2:
                        zones.append({'type': 'EQUAL_LOW', 'price': level, 'touches': touches})
            
            return zones
            
        except Exception as e:
            self._log_with_context('error', f"Liquidity zones error: {e}", symbol)
            return []
    
    def calculate_liquidity_state(
        self,
        candles: List[Dict],
        current_price: float,
        symbol: str = None
    ) -> str:
        """
        Calculate liquidity state (NEAR_PDH, NEAR_PDL, BETWEEN, AWAY).
        
        Args:
            candles: List of candle dicts
            current_price: Current price
            symbol: Symbol name for logging
            
        Returns:
            Liquidity state string
        """
        try:
            if len(candles) < 20:
                return 'AWAY'
            
            # Get liquidity zones
            zones = self.identify_liquidity_zones(candles, symbol)
            
            if not zones:
                return 'AWAY'
            
            # Find PDH and PDL
            pdh = None
            pdl = None
            
            for zone in zones:
                if zone['type'] == 'PDH':
                    pdh = zone['price']
                elif zone['type'] == 'PDL':
                    pdl = zone['price']
            
            if not pdh or not pdl:
                return 'AWAY'
            
            # Calculate tolerance (0.5% of price range)
            price_range = pdh - pdl
            tolerance = price_range * 0.005
            
            # Check proximity
            near_pdh = abs(current_price - pdh) <= tolerance
            near_pdl = abs(current_price - pdl) <= tolerance
            
            if near_pdh:
                return 'NEAR_PDH'
            elif near_pdl:
                return 'NEAR_PDL'
            elif pdl < current_price < pdh:
                return 'BETWEEN'
            else:
                return 'AWAY'
            
        except Exception as e:
            self._log_with_context('error', f"Liquidity state error: {e}", symbol)
            return 'AWAY'
    
    def calculate_volatility_state(self, candles: List[Dict], symbol: str = None) -> Dict[str, Any]:
        """
        Calculate volatility state (CONTRACTING, EXPANDING, STABLE).
        
        Args:
            candles: List of candle dicts
            symbol: Symbol name for logging
            
        Returns:
            Volatility state dict
        """
        try:
            if len(candles) < 20:
                return {
                    'state': 'STABLE',
                    'change_pct': 0,
                    'atr': 0,
                    'atr_median': 0,
                    'squeeze_duration': 0
                }
            
            # Calculate ATR
            atr_current = self._calculate_atr(candles[-14:], period=14)
            
            # Calculate median ATR over longer period
            if len(candles) >= 50:
                atr_values = []
                for i in range(len(candles) - 50, len(candles) - 14):
                    atr_val = self._calculate_atr(candles[i:i+14], period=14)
                    if atr_val > 0:
                        atr_values.append(atr_val)
                
                atr_median = statistics.median(atr_values) if atr_values else atr_current
            else:
                atr_median = atr_current
            
            if atr_median <= 0:
                atr_median = atr_current if atr_current > 0 else 1.0
            
            # Calculate change percentage
            change_pct = ((atr_current - atr_median) / atr_median) * 100
            
            # Determine state
            if change_pct < -20:
                state = 'CONTRACTING'
            elif change_pct > 20:
                state = 'EXPANDING'
            else:
                state = 'STABLE'
            
            # Calculate squeeze duration (consecutive contracting periods)
            squeeze_duration = 0
            if state == 'CONTRACTING':
                # Count how many recent periods were contracting
                for i in range(len(candles) - 20, len(candles) - 14):
                    if i >= 0:
                        period_atr = self._calculate_atr(candles[i:i+14], period=14)
                        if period_atr < atr_median * 0.8:  # 20% below median
                            squeeze_duration += 1
            
            return {
                'state': state,
                'change_pct': round(change_pct, 2),
                'atr': atr_current,
                'atr_median': atr_median,
                'squeeze_duration': squeeze_duration
            }
            
        except Exception as e:
            self._log_with_context('error', f"Volatility state error: {e}", symbol)
            return {
                'state': 'STABLE',
                'change_pct': 0,
                'atr': 0,
                'atr_median': 0,
                'squeeze_duration': 0
            }
    
    def detect_rejection_wicks(self, candles: List[Dict], symbol: str = None) -> List[Dict[str, Any]]:
        """
        Detect rejection wicks (upper and lower).
        
        Args:
            candles: List of candle dicts
            symbol: Symbol name for logging
            
        Returns:
            List of rejection wick dicts
        """
        try:
            if len(candles) < 5:
                return []
            
            rejections = []
            
            # Check last 10 candles for rejection wicks
            recent = candles[-10:] if len(candles) >= 10 else candles
            
            for candle in recent:
                open_price = candle.get('open', 0)
                high = candle.get('high', 0)
                low = candle.get('low', 0)
                close = candle.get('close', 0)
                
                if open_price <= 0 or high <= 0 or low <= 0 or close <= 0:
                    continue
                
                body_size = abs(close - open_price)
                upper_wick = high - max(open_price, close)
                lower_wick = min(open_price, close) - low
                total_range = high - low
                
                if total_range <= 0:
                    continue
                
                wick_ratio = upper_wick / total_range if total_range > 0 else 0
                body_ratio = body_size / total_range if total_range > 0 else 0
                
                # Upper rejection: wick > 60% of range, body < 40%
                if wick_ratio > 0.6 and body_ratio < 0.4:
                    rejections.append({
                        'type': 'UPPER',
                        'price': high,
                        'wick_ratio': round(wick_ratio, 2),
                        'body_ratio': round(body_ratio, 2),
                        'timestamp': candle.get('timestamp')
                    })
                
                # Lower rejection: wick > 60% of range, body < 40%
                wick_ratio_lower = lower_wick / total_range if total_range > 0 else 0
                if wick_ratio_lower > 0.6 and body_ratio < 0.4:
                    rejections.append({
                        'type': 'LOWER',
                        'price': low,
                        'wick_ratio': round(wick_ratio_lower, 2),
                        'body_ratio': round(body_ratio, 2),
                        'timestamp': candle.get('timestamp')
                    })
            
            return rejections
            
        except Exception as e:
            self._log_with_context('error', f"Rejection wicks error: {e}", symbol)
            return []
    
    def find_order_blocks(self, candles: List[Dict], symbol: str = None) -> List[Dict[str, Any]]:
        """
        Find order blocks (institutional order zones).
        
        Args:
            candles: List of candle dicts
            symbol: Symbol name for logging
            
        Returns:
            List of order block dicts
        """
        try:
            if len(candles) < 10:
                return []
            
            order_blocks = []
            
            # Look for strong moves followed by consolidation
            for i in range(10, len(candles)):
                # Check for strong bullish move
                prev_candle = candles[i-1]
                curr_candle = candles[i]
                
                prev_body = abs(prev_candle.get('close', 0) - prev_candle.get('open', 0))
                curr_body = abs(curr_candle.get('close', 0) - curr_candle.get('open', 0))
                
                # Use minimum body size to handle doji candles (open == close)
                # Doji candles represent strong consolidation/indecision, which is valid for order blocks
                min_body_size = 0.0001  # Very small threshold to avoid division by zero
                effective_curr_body = max(curr_body, min_body_size)
                
                # Strong bullish candle followed by small body (consolidation)
                # Note: Doji candles (curr_body == 0) are valid - they show strong consolidation
                if (prev_candle.get('close', 0) > prev_candle.get('open', 0) and
                    prev_body > effective_curr_body * 2 and
                    curr_body < prev_body * 0.5):
                    
                    # Calculate strength: ratio of prev_body to curr_body
                    # For doji candles (curr_body = 0), use min_body_size to get maximum strength
                    strength_ratio = prev_body / effective_curr_body
                    strength = min(100, int(strength_ratio * 10))
                    
                    order_blocks.append({
                        'type': 'BULLISH',
                        'price_range': [
                            min(prev_candle.get('low', 0), curr_candle.get('low', 0)),
                            max(prev_candle.get('high', 0), curr_candle.get('high', 0))
                        ],
                        'strength': strength,
                        'is_doji': curr_body == 0  # Flag to indicate if this is a doji-based order block
                    })
                
                # Strong bearish candle followed by small body (consolidation)
                # Note: Doji candles (curr_body == 0) are valid - they show strong consolidation
                if (prev_candle.get('close', 0) < prev_candle.get('open', 0) and
                    prev_body > effective_curr_body * 2 and
                    curr_body < prev_body * 0.5):
                    
                    # Calculate strength: ratio of prev_body to curr_body
                    # For doji candles (curr_body = 0), use min_body_size to get maximum strength
                    strength_ratio = prev_body / effective_curr_body
                    strength = min(100, int(strength_ratio * 10))
                    
                    order_blocks.append({
                        'type': 'BEARISH',
                        'price_range': [
                            min(prev_candle.get('low', 0), curr_candle.get('low', 0)),
                            max(prev_candle.get('high', 0), curr_candle.get('high', 0))
                        ],
                        'strength': strength,
                        'is_doji': curr_body == 0  # Flag to indicate if this is a doji-based order block
                    })
            
            # Return most recent order blocks
            return order_blocks[-5:] if len(order_blocks) > 5 else order_blocks
            
        except Exception as e:
            self._log_with_context('error', f"Order blocks error: {e}", symbol)
            return []
    
    def calculate_momentum_quality(
        self,
        candles: List[Dict],
        include_rsi: bool = True,
        symbol: str = None
    ) -> Dict[str, Any]:
        """
        Calculate momentum quality (EXCELLENT, GOOD, FAIR, CHOPPY).
        
        Includes RSI validation if include_rsi=True.
        
        Args:
            candles: List of candle dicts
            include_rsi: Include RSI > 40 validation (default: True)
            symbol: Symbol name for logging
            
        Returns:
            Momentum quality dict
        """
        try:
            if len(candles) < 14:
                return {
                    'quality': 'CHOPPY',
                    'consistency': 0,
                    'consecutive_moves': 0,
                    'rsi_validation': False,
                    'rsi_value': 0
                }
            
            # Calculate consecutive moves in same direction
            consecutive_moves = 0
            direction = None
            
            for i in range(len(candles) - 10, len(candles)):
                if i <= 0:
                    continue
                
                prev_close = candles[i-1].get('close', 0)
                curr_close = candles[i].get('close', 0)
                
                if prev_close <= 0 or curr_close <= 0:
                    continue
                
                if curr_close > prev_close:
                    if direction == 'UP' or direction is None:
                        consecutive_moves += 1
                        direction = 'UP'
                    else:
                        consecutive_moves = 1
                        direction = 'UP'
                elif curr_close < prev_close:
                    if direction == 'DOWN' or direction is None:
                        consecutive_moves += 1
                        direction = 'DOWN'
                    else:
                        consecutive_moves = 1
                        direction = 'DOWN'
                else:
                    consecutive_moves = 0
                    direction = None
            
            # Calculate consistency (how often price moves in same direction)
            consistency = min(100, consecutive_moves * 10)
            
            # Calculate RSI if requested
            rsi_value = 0
            rsi_validation = False
            
            if include_rsi:
                rsi_value = self._calculate_rsi(candles, period=14)
                rsi_validation = rsi_value > 40  # RSI > 40 validation
            
            # Determine quality
            if consecutive_moves >= 5 and consistency >= 70 and (not include_rsi or rsi_validation):
                quality = 'EXCELLENT'
            elif consecutive_moves >= 3 and consistency >= 50 and (not include_rsi or rsi_validation):
                quality = 'GOOD'
            elif consecutive_moves >= 2 and consistency >= 30:
                quality = 'FAIR'
            else:
                quality = 'CHOPPY'
            
            return {
                'quality': quality,
                'consistency': consistency,
                'consecutive_moves': consecutive_moves,
                'rsi_validation': rsi_validation,
                'rsi_value': round(rsi_value, 2) if rsi_value > 0 else 0
            }
            
        except Exception as e:
            self._log_with_context('error', f"Momentum quality error: {e}", symbol)
            return {
                'quality': 'CHOPPY',
                'consistency': 0,
                'consecutive_moves': 0,
                'rsi_validation': False,
                'rsi_value': 0
            }
    
    def trend_context(
        self,
        candles: List[Dict],
        higher_timeframe_data: Dict[str, Any],
        include_m15: bool = False,
        symbol: str = None
    ) -> Dict[str, Any]:
        """
        Calculate trend context (M1 alignment with M5/H1/M15).
        
        Args:
            candles: List of M1 candle dicts
            higher_timeframe_data: Dict with M5/H1 data
            include_m15: Include M15 alignment (optional)
            symbol: Symbol name for logging
            
        Returns:
            Trend context dict
        """
        try:
            if not higher_timeframe_data:
                return {
                    'alignment': 'UNKNOWN',
                    'confidence': 0,
                    'm1_m5_alignment': False,
                    'm1_h1_alignment': False,
                    'm1_m15_alignment': False
                }
            
            # Get M1 trend
            m1_structure = self.analyze_structure(candles, symbol)
            m1_trend = m1_structure.get('type', 'UNKNOWN')
            
            # Get M5 trend
            m5_data = higher_timeframe_data.get('m5', {})
            m5_trend = m5_data.get('trend', 'UNKNOWN') if isinstance(m5_data, dict) else 'UNKNOWN'
            
            # Get H1 trend
            h1_data = higher_timeframe_data.get('h1', {})
            h1_trend = h1_data.get('trend', 'UNKNOWN') if isinstance(h1_data, dict) else 'UNKNOWN'
            
            # Check alignment
            m1_m5_alignment = self._trends_align(m1_trend, m5_trend)
            m1_h1_alignment = self._trends_align(m1_trend, h1_trend)
            m1_m15_alignment = False
            
            if include_m15:
                m15_data = higher_timeframe_data.get('m15', {})
                m15_trend = m15_data.get('trend', 'UNKNOWN') if isinstance(m15_data, dict) else 'UNKNOWN'
                m1_m15_alignment = self._trends_align(m1_trend, m15_trend)
            
            # Calculate alignment strength
            alignment_count = sum([m1_m5_alignment, m1_h1_alignment, m1_m15_alignment if include_m15 else False])
            
            if alignment_count >= 2:
                alignment = 'STRONG'
                confidence = 90
            elif alignment_count == 1:
                alignment = 'MODERATE'
                confidence = 60
            else:
                alignment = 'WEAK'
                confidence = 30
            
            return {
                'alignment': alignment,
                'confidence': confidence,
                'm1_m5_alignment': m1_m5_alignment,
                'm1_h1_alignment': m1_h1_alignment,
                'm1_m15_alignment': m1_m15_alignment
            }
            
        except Exception as e:
            self._log_with_context('error', f"Trend context error: {e}", symbol)
            return {
                'alignment': 'UNKNOWN',
                'confidence': 0,
                'm1_m5_alignment': False,
                'm1_h1_alignment': False,
                'm1_m15_alignment': False
            }
    
    def generate_signal_summary(self, analysis: Dict, symbol: str = None) -> str:
        """
        Generate simplified signal summary.
        
        Args:
            analysis: Complete analysis dict
            symbol: Symbol name for logging
            
        Returns:
            Signal summary string: "BULLISH_MICROSTRUCTURE" | "BEARISH_MICROSTRUCTURE" | "NEUTRAL"
        """
        try:
            choch_bos = analysis.get('choch_bos', {})
            structure = analysis.get('structure', {})
            
            has_choch = choch_bos.get('has_choch', False)
            has_bos = choch_bos.get('has_bos', False)
            structure_type = structure.get('type', 'UNKNOWN')
            
            # Determine signal
            if has_choch or has_bos:
                if structure_type in ['HIGHER_HIGH', 'EQUAL']:
                    return 'BULLISH_MICROSTRUCTURE'
                elif structure_type == 'LOWER_LOW':
                    return 'BEARISH_MICROSTRUCTURE'
                else:
                    # Use CHOCH/BOS direction
                    if choch_bos.get('choch_confirmed', False):
                        # Determine direction from price action
                        # This is simplified - in practice, check actual break direction
                        return 'BULLISH_MICROSTRUCTURE'  # Default, should be improved
            else:
                return 'NEUTRAL'
            
            return 'NEUTRAL'
            
        except Exception as e:
            self._log_with_context('error', f"Signal summary error: {e}", symbol)
            return 'NEUTRAL'
    
    def calculate_signal_age(self, signal_timestamp: Optional[str]) -> float:
        """
        Calculate signal age in seconds.
        
        Args:
            signal_timestamp: ISO format timestamp string or None
            
        Returns:
            Age in seconds, or 0 if no timestamp
        """
        if not signal_timestamp:
            return 0.0
        
        try:
            if isinstance(signal_timestamp, str):
                # Parse ISO format
                if 'T' in signal_timestamp:
                    signal_time = datetime.fromisoformat(signal_timestamp.replace('Z', '+00:00'))
                else:
                    signal_time = datetime.fromisoformat(signal_timestamp)
            else:
                signal_time = signal_timestamp
            
            # Ensure timezone-aware
            if signal_time.tzinfo is None:
                signal_time = signal_time.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            age_seconds = (now - signal_time).total_seconds()
            
            return max(0.0, age_seconds)
            
        except Exception as e:
            self._log_with_context('warning', f"Signal age calculation error: {e}", None)
            return 0.0
    
    def is_signal_stale(self, signal_timestamp: Optional[str], max_age_seconds: int = 300) -> bool:
        """
        Check if signal is stale.
        
        Args:
            signal_timestamp: ISO format timestamp string or None
            max_age_seconds: Maximum age in seconds (default: 300 = 5 minutes)
            
        Returns:
            True if stale, False if fresh
        """
        age = self.calculate_signal_age(signal_timestamp)
        return age > max_age_seconds
    
    def generate_strategy_hint(self, analysis: Dict, session: str = None) -> str:
        """
        Generate strategy hint based on microstructure conditions.
        
        Args:
            analysis: Complete analysis dict
            session: Current session (optional)
            
        Returns:
            Strategy hint: "RANGE_SCALP" | "BREAKOUT" | "REVERSAL" | "TREND_CONTINUATION"
        """
        try:
            volatility = analysis.get('volatility', {})
            structure = analysis.get('structure', {})
            momentum = analysis.get('momentum', {})
            trend_context = analysis.get('trend_context', {})
            
            vol_state = volatility.get('state', 'STABLE')
            structure_type = structure.get('type', 'CHOPPY')
            momentum_quality = momentum.get('quality', 'CHOPPY')
            alignment = trend_context.get('alignment', 'WEAK')
            
            # RANGE_SCALP: CHOPPY structure + CONTRACTING volatility
            if structure_type == 'CHOPPY' and vol_state == 'CONTRACTING':
                return 'RANGE_SCALP'
            
            # BREAKOUT: CONTRACTING + squeeze duration > threshold
            if vol_state == 'CONTRACTING' and volatility.get('squeeze_duration', 0) > 20:
                return 'BREAKOUT'
            
            # REVERSAL: EXPANDING + exhaustion (choppy momentum after expansion)
            if vol_state == 'EXPANDING' and momentum_quality == 'CHOPPY':
                return 'REVERSAL'
            
            # TREND_CONTINUATION: STRONG alignment + EXCELLENT momentum
            if alignment == 'STRONG' and momentum_quality == 'EXCELLENT':
                return 'TREND_CONTINUATION'
            
            # Default based on structure
            if structure_type in ['HIGHER_HIGH', 'LOWER_LOW']:
                return 'TREND_CONTINUATION'
            else:
                return 'RANGE_SCALP'
            
        except Exception as e:
            self._log_with_context('error', f"Strategy hint error: {e}", None)
            return 'RANGE_SCALP'
    
    def _get_vwap_state(self, symbol: str, candles: List[Dict]) -> str:
        """
        Get VWAP state (NEUTRAL, STRETCHED, ALIGNED, REVERSION).
        
        Args:
            symbol: Symbol name
            candles: List of candle dicts
            
        Returns:
            VWAP state string
        """
        try:
            if len(candles) < 20:
                return 'NEUTRAL'
            
            # Calculate VWAP
            vwap = self._calculate_vwap(candles)
            if vwap <= 0:
                return 'NEUTRAL'
            
            current_price = candles[-1].get('close', 0)
            if current_price <= 0:
                return 'NEUTRAL'
            
            # Calculate distance from VWAP (avoid division by zero)
            if vwap == 0:
                return 'NEUTRAL'
            distance_pct = abs(current_price - vwap) / vwap * 100
            
            # Determine state
            if distance_pct < 0.5:
                return 'NEUTRAL'
            elif distance_pct > 2.0:
                return 'STRETCHED'
            elif current_price > vwap:
                return 'ALIGNED'  # Price above VWAP in uptrend
            else:
                return 'REVERSION'  # Price below VWAP, potential mean reversion
            
        except Exception as e:
            self._log_with_context('warning', f"VWAP state error: {e}", symbol)
            return 'NEUTRAL'
    
    def calculate_microstructure_confluence(
        self,
        analysis: Dict,
        session: str = None,
        symbol: str = None,
        volatility_regime: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate microstructure confluence score (0-100).
        
        Blends multiple factors into standardized score.
        
        Args:
            analysis: Complete analysis dict
            session: Current session (optional)
            symbol: Symbol name for logging
            volatility_regime: Optional volatility regime (STABLE/TRANSITIONAL/VOLATILE) for BTC
            
        Returns:
            Confluence dict with score, grade, recommended_action, and components
        """
        try:
            # Component scores (0-100 each)
            components = {}
            
            # 1. M1 Signal Confidence
            choch_bos = analysis.get('choch_bos', {})
            signal_confidence = choch_bos.get('confidence', 0)
            components['m1_signal_confidence'] = signal_confidence
            
            # 2. Session Volatility Suitability
            # For BTC: Use volatility regime instead of session-based volatility tier
            # For XAU and others: Use session-based volatility tier
            is_btc = symbol and symbol.upper().startswith('BTC')
            
            # Fix 14: Regime String Validation
            VALID_VOLATILITY_REGIMES = {'STABLE', 'TRANSITIONAL', 'VOLATILE'}
            
            if is_btc and volatility_regime:
                # Validate regime string before use
                regime_upper = volatility_regime.upper() if isinstance(volatility_regime, str) else None
                if regime_upper not in VALID_VOLATILITY_REGIMES:
                    logger.warning(
                        f"Invalid volatility regime '{volatility_regime}' for {symbol}, "
                        f"falling back to session-based volatility tier"
                    )
                    volatility_regime = None
                    regime_upper = None
                
                if regime_upper:
                    # BTC: Map volatility regime to suitability score
                    # STABLE = NORMAL volatility (good for trading)
                    # TRANSITIONAL = MODERATE volatility (acceptable)
                    # VOLATILE = HIGH volatility (risky but can be profitable)
                    regime_suitability = {
                        'STABLE': 80,        # Normal trading conditions
                        'TRANSITIONAL': 75,  # Moderate volatility
                        'VOLATILE': 85       # High volatility (can be good for BTC)
                    }.get(regime_upper, 80)
                    components['session_volatility_suitability'] = regime_suitability
                else:
                    # Fall through to session-based logic
                    is_btc = False
            
            if not is_btc or not volatility_regime:
                # XAU and others: Use session-based volatility tier
                session_context = analysis.get('session_context', {})
                volatility_tier = session_context.get('volatility_tier', 'NORMAL')
                session_suitability = {
                    'LOW': 60,
                    'NORMAL': 80,
                    'HIGH': 90,
                    'VERY_HIGH': 95
                }.get(volatility_tier, 70)
                components['session_volatility_suitability'] = session_suitability
            
            # 3. Momentum Quality
            momentum = analysis.get('momentum', {})
            momentum_quality = momentum.get('quality', 'CHOPPY')
            momentum_score = {
                'EXCELLENT': 95,
                'GOOD': 80,
                'FAIR': 60,
                'CHOPPY': 40
            }.get(momentum_quality, 50)
            components['momentum_quality'] = momentum_score
            
            # 4. Liquidity Proximity
            liquidity_state = analysis.get('liquidity_state', 'AWAY')
            liquidity_score = {
                'NEAR_PDH': 80,
                'NEAR_PDL': 80,
                'BETWEEN': 70,
                'AWAY': 50
            }.get(liquidity_state, 50)
            components['liquidity_proximity'] = liquidity_score
            
            # 5. Strategy Fit
            strategy_hint = analysis.get('strategy_hint', 'RANGE_SCALP')
            trend_context = analysis.get('trend_context', {})
            alignment = trend_context.get('alignment', 'WEAK')
            
            strategy_fit = 70  # Base
            if alignment == 'STRONG':
                strategy_fit += 20
            elif alignment == 'MODERATE':
                strategy_fit += 10
            
            components['strategy_fit'] = strategy_fit
            
            # Calculate weighted average
            weights = {
                'm1_signal_confidence': 0.30,
                'session_volatility_suitability': 0.20,
                'momentum_quality': 0.25,
                'liquidity_proximity': 0.15,
                'strategy_fit': 0.10
            }
            
            base_score = sum(components[key] * weights[key] for key in components.keys())
            base_score = max(0, min(100, base_score))  # Clamp to 0-100
            
            # Store base score before adjustments
            components['base_score'] = base_score
            
            # Apply session/asset adjustments if available
            adjusted_score = base_score
            session_bias = analysis.get('session_context', {}).get('session_bias_factor', 1.0)
            if session_bias != 1.0:
                adjusted_score = base_score * session_bias
                adjusted_score = max(0, min(100, adjusted_score))
            
            # Determine grade
            if adjusted_score >= 90:
                grade = 'A'
            elif adjusted_score >= 80:
                grade = 'B'
            elif adjusted_score >= 70:
                grade = 'C'
            elif adjusted_score >= 60:
                grade = 'D'
            else:
                grade = 'F'
            
            # Determine recommended action
            signal_summary = analysis.get('signal_summary', 'NEUTRAL')
            if adjusted_score >= 75:
                if signal_summary == 'BULLISH_MICROSTRUCTURE':
                    recommended_action = 'BUY_CONFIRMED'
                elif signal_summary == 'BEARISH_MICROSTRUCTURE':
                    recommended_action = 'SELL_CONFIRMED'
                else:
                    recommended_action = 'WAIT'
            elif adjusted_score >= 60:
                recommended_action = 'WAIT'
            else:
                recommended_action = 'AVOID'
            
            return {
                'score': round(adjusted_score, 1),
                'base_score': round(base_score, 1),
                'grade': grade,
                'recommended_action': recommended_action,
                'components': components
            }
            
        except Exception as e:
            self._log_with_context('error', f"Confluence calculation error: {e}", symbol)
            return {
                'score': 0,
                'base_score': 0,
                'grade': 'F',
                'recommended_action': 'AVOID',
                'components': {}
            }
    
    # Helper methods
    
    def _calculate_atr(self, candles: List[Dict], period: int = 14) -> float:
        """Calculate Average True Range."""
        try:
            if len(candles) < period + 1:
                return 0.0
            
            true_ranges = []
            for i in range(1, len(candles)):
                high = candles[i].get('high', 0)
                low = candles[i].get('low', 0)
                prev_close = candles[i-1].get('close', 0)
                
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)
            
            if not true_ranges:
                return 0.0
            
            # Use last 'period' true ranges
            recent_tr = true_ranges[-period:] if len(true_ranges) >= period else true_ranges
            return statistics.mean(recent_tr)
            
        except Exception:
            return 0.0
    
    def _calculate_rsi(self, candles: List[Dict], period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        try:
            if len(candles) < period + 1:
                return 0.0
            
            closes = [c.get('close', 0) for c in candles[-period-1:]]
            
            gains = []
            losses = []
            
            for i in range(1, len(closes)):
                change = closes[i] - closes[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            if not gains or not losses:
                return 50.0  # Neutral RSI
            
            avg_gain = statistics.mean(gains) if gains else 0
            avg_loss = statistics.mean(losses) if losses else 0.0001  # Avoid division by zero
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return max(0, min(100, rsi))
            
        except Exception:
            return 50.0
    
    def _calculate_vwap(self, candles: List[Dict]) -> float:
        """Calculate Volume Weighted Average Price."""
        try:
            if not candles:
                return 0.0
            
            total_volume_price = 0
            total_volume = 0
            
            for candle in candles:
                volume = candle.get('volume', 0)
                typical_price = (candle.get('high', 0) + candle.get('low', 0) + candle.get('close', 0)) / 3
                
                total_volume_price += typical_price * volume
                total_volume += volume
            
            if total_volume <= 0:
                # Fallback to simple average
                prices = [c.get('close', 0) for c in candles]
                return statistics.mean(prices) if prices else 0.0
            
            # Avoid division by zero
            if total_volume == 0:
                # Fallback to simple average if no volume data
                prices = [c.get('close', 0) for c in candles]
                return statistics.mean(prices) if prices else 0.0
            return total_volume_price / total_volume
            
        except Exception:
            return 0.0
    
    def _find_equal_levels(self, levels: List[float], tolerance: float) -> Dict[float, int]:
        """Find equal price levels within tolerance."""
        clusters = {}
        
        for level in levels:
            # Find existing cluster within tolerance
            found_cluster = False
            for cluster_level in clusters.keys():
                if abs(level - cluster_level) <= tolerance:
                    clusters[cluster_level] += 1
                    found_cluster = True
                    break
            
            if not found_cluster:
                clusters[level] = 1
        
        return clusters
    
    def _trends_align(self, trend1: str, trend2: str) -> bool:
        """Check if two trends align."""
        bullish = ['HIGHER_HIGH', 'UP', 'BULLISH']
        bearish = ['LOWER_LOW', 'DOWN', 'BEARISH']
        
        if trend1 in bullish and trend2 in bullish:
            return True
        if trend1 in bearish and trend2 in bearish:
            return True
        
        return False
    
    def _get_structure_alignment(self, structure: Dict) -> str:
        """Get structure alignment string for strategy selector."""
        structure_type = structure.get('type', 'CHOPPY')
        
        if structure_type == 'HIGHER_HIGH':
            return 'uptrend'
        elif structure_type == 'LOWER_LOW':
            return 'downtrend'
        elif structure_type == 'CHOPPY':
            return 'range'
        else:
            return 'range'
    
    def _get_volatility_tier(self, volatility: Dict) -> str:
        """Get volatility tier from volatility state."""
        change_pct = volatility.get('change_pct', 0)
        
        if change_pct < -30:
            return 'LOW'
        elif change_pct < 30:
            return 'NORMAL'
        elif change_pct < 60:
            return 'HIGH'
        else:
            return 'VERY_HIGH'
    
    def _get_liquidity_timing(self, session: str) -> str:
        """Get liquidity timing for session."""
        timing_map = {
            'ASIAN': 'LOW',
            'LONDON': 'ACTIVE',
            'NY': 'ACTIVE',
            'OVERLAP': 'ACTIVE',
            'POST_NY': 'MODERATE'
        }
        return timing_map.get(session, 'MODERATE')
    
    def get_microstructure(self, symbol: str) -> Dict[str, Any]:
        """
        Convenience method to get microstructure analysis.
        
        This method should be called by external systems (desktop_agent, etc.)
        It will fetch M1 data and perform complete analysis.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Complete analysis dict
        """
        # This method will be implemented when M1DataFetcher is integrated
        # For now, return placeholder
        return {
            'available': False,
            'error': 'M1DataFetcher not integrated yet'
        }
    
    # =====================================
    # Phase 4.2: Caching Methods
    # =====================================
    
    def _get_cache_key(self, symbol: str, candles: List[Dict[str, Any]]) -> Optional[str]:
        """
        Generate cache key from symbol and candle data.
        
        Cache key includes:
        - Symbol name
        - Last candle timestamp (to detect new candles)
        - Candle count (to detect data changes)
        
        Args:
            symbol: Symbol name
            candles: List of candle dicts
            
        Returns:
            Cache key string or None if candles invalid
        """
        if not candles or len(candles) == 0:
            return None
        
        try:
            last_candle = candles[-1]
            last_timestamp = last_candle.get('timestamp')
            
            # Convert timestamp to string if it's a datetime
            if isinstance(last_timestamp, datetime):
                last_timestamp = last_timestamp.isoformat()
            elif last_timestamp is None:
                return None
            
            # Create cache key: symbol_timestamp_count
            cache_key = f"{symbol}_{last_timestamp}_{len(candles)}"
            return cache_key
        except Exception as e:
            logger.warning(f"Error generating cache key: {e}")
            return None
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached analysis result if valid.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached result or None if not found/expired
        """
        if cache_key not in self._analysis_cache:
            return None
        
        # Check TTL
        cache_time = self._cache_timestamps.get(cache_key, 0)
        if time.time() - cache_time > self._cache_ttl:
            # Cache expired, remove it
            self._analysis_cache.pop(cache_key, None)
            self._cache_timestamps.pop(cache_key, None)
            return None
        
        return self._analysis_cache.get(cache_key)
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """
        Cache analysis result.
        
        Args:
            cache_key: Cache key
            result: Analysis result to cache
        """
        try:
            # Cleanup if cache is too large
            if len(self._analysis_cache) >= self._cache_max_size:
                self._cleanup_cache()
            
            # Cache the result
            self._analysis_cache[cache_key] = result
            self._cache_timestamps[cache_key] = time.time()
            
            logger.debug(f"Cached analysis result for key: {cache_key}")
        except Exception as e:
            logger.warning(f"Error caching result: {e}")
    
    def _cleanup_cache(self):
        """
        Clean up expired cache entries.
        Removes oldest entries if cache is full.
        """
        try:
            current_time = time.time()
            
            # Remove expired entries
            expired_keys = []
            for key, cache_time in self._cache_timestamps.items():
                if current_time - cache_time > self._cache_ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._analysis_cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
            
            # If still too large, remove oldest entries
            if len(self._analysis_cache) >= self._cache_max_size:
                # Sort by timestamp and remove oldest
                sorted_keys = sorted(
                    self._cache_timestamps.items(),
                    key=lambda x: x[1]
                )
                
                # Remove oldest 20% of entries
                remove_count = max(1, len(sorted_keys) // 5)
                for key, _ in sorted_keys[:remove_count]:
                    self._analysis_cache.pop(key, None)
                    self._cache_timestamps.pop(key, None)
                
                logger.debug(f"Cleaned up {remove_count} cache entries")
        except Exception as e:
            logger.warning(f"Error cleaning up cache: {e}")

