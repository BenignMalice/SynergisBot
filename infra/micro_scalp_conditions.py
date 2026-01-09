"""
Micro-Scalp Conditions Checker

Implements the 4-layer structured condition system:
1. Pre-Trade Filters (hard blocks)
2. Location Filter (must be at "EDGE")
3. Candle Signal Checklist (primary + secondary)
4. Confluence Score (numeric filter)
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from infra.micro_scalp_volatility_filter import MicroScalpVolatilityFilter, VolatilityFilterResult
from infra.vwap_micro_filter import VWAPMicroFilter, VWAPProximityResult, VWAPRetestResult
from infra.micro_liquidity_sweep_detector import MicroLiquiditySweepDetector, MicroSweepResult
from infra.micro_order_block_detector import MicroOrderBlockDetector, MicroOrderBlock
from infra.spread_tracker import SpreadTracker, SpreadData

logger = logging.getLogger(__name__)


@dataclass
class ConditionCheckResult:
    """Result of condition checking"""
    passed: bool
    pre_trade_passed: bool
    location_passed: bool
    primary_triggers: int
    secondary_confluence: int
    confluence_score: float
    is_aplus_setup: bool
    reasons: List[str]
    details: Dict[str, Any]


class MicroScalpConditionsChecker:
    """
    4-layer condition system for micro-scalp validation.
    
    Layers:
    1. Pre-Trade Filters (hard blocks - must pass all)
    2. Location Filter (must be at "EDGE")
    3. Candle Signal Checklist (primary + secondary)
    4. Confluence Score (numeric filter)
    """
    
    def __init__(self, config: Dict[str, Any],
                 volatility_filter: MicroScalpVolatilityFilter,
                 vwap_filter: VWAPMicroFilter,
                 sweep_detector: MicroLiquiditySweepDetector,
                 ob_detector: MicroOrderBlockDetector,
                 spread_tracker: SpreadTracker,
                 m1_analyzer=None,
                 session_manager=None):
        """
        Initialize Micro-Scalp Conditions Checker.
        
        Args:
            config: Configuration dict
            volatility_filter: MicroScalpVolatilityFilter instance
            vwap_filter: VWAPMicroFilter instance
            sweep_detector: MicroLiquiditySweepDetector instance
            ob_detector: MicroOrderBlockDetector instance
            spread_tracker: SpreadTracker instance
            m1_analyzer: Optional M1MicrostructureAnalyzer instance
            session_manager: Optional session manager for session data
        """
        self.config = config
        self.volatility_filter = volatility_filter
        self.vwap_filter = vwap_filter
        self.sweep_detector = sweep_detector
        self.ob_detector = ob_detector
        self.spread_tracker = spread_tracker
        self.m1_analyzer = m1_analyzer
        self.session_manager = session_manager
    
    def validate(self, snapshot: Dict[str, Any]) -> ConditionCheckResult:
        """
        Validate micro-scalp conditions using 4-layer system.
        
        Args:
            snapshot: Snapshot dict with:
                - symbol: Trading symbol
                - candles: List of M1 candles
                - current_price: Current price (bid/ask)
                - vwap: Current VWAP value
                - atr1: Optional ATR(1) value
                - spread_data: Optional SpreadData
                - btc_order_flow: Optional BTC order flow metrics (for BTCUSD)
        
        Returns:
            ConditionCheckResult
        """
        symbol = snapshot.get('symbol', '')
        candles = snapshot.get('candles', [])
        current_price = snapshot.get('current_price', 0.0)
        vwap = snapshot.get('vwap', 0.0)
        atr1 = snapshot.get('atr1')
        spread_data = snapshot.get('spread_data')
        btc_order_flow = snapshot.get('btc_order_flow')
        
        reasons = []
        details = {}
        
        # 1️⃣ Pre-Trade Filters (Hard Blocks)
        pre_trade_result = self._check_pre_trade_filters(
            symbol, candles, spread_data, current_price
        )
        pre_trade_passed = pre_trade_result.passed
        details['pre_trade'] = {
            'passed': pre_trade_passed,
            'atr1': pre_trade_result.atr1_value,
            'm1_range_avg': pre_trade_result.m1_range_avg,
            'reasons': pre_trade_result.reasons
        }
        
        if not pre_trade_passed:
            reasons.extend(pre_trade_result.reasons)
            return ConditionCheckResult(
                passed=False,
                pre_trade_passed=False,
                location_passed=False,
                primary_triggers=0,
                secondary_confluence=0,
                confluence_score=0.0,
                is_aplus_setup=False,
                reasons=reasons,
                details=details
            )
        
        # 2️⃣ Location Filter (Must be at "EDGE")
        location_result = self._check_location_filter(
            symbol, candles, current_price, vwap, atr1
        )
        location_passed = location_result['passed']
        details['location'] = location_result
        
        if not location_passed:
            reasons.append("Not at edge location (mid-range)")
            return ConditionCheckResult(
                passed=False,
                pre_trade_passed=True,
                location_passed=False,
                primary_triggers=0,
                secondary_confluence=0,
                confluence_score=0.0,
                is_aplus_setup=False,
                reasons=reasons,
                details=details
            )
        
        # 3️⃣ Candle Signal Checklist
        signal_result = self._check_candle_signals(
            symbol, candles, current_price, vwap, atr1, btc_order_flow
        )
        primary_count = signal_result['primary_count']
        secondary_count = signal_result['secondary_count']
        primary_triggers = signal_result.get('primary_triggers', [])
        secondary_confluence = signal_result.get('secondary_confluence', [])
        details['signals'] = signal_result
        
        if primary_count < 1 or secondary_count < 1:
            # Build detailed failure message with signal names
            failure_msg = f"Insufficient signals: {primary_count} primary, {secondary_count} secondary (need ≥1 each)"
            if primary_count > 0:
                failure_msg += f" - Primary: {', '.join(primary_triggers)}"
            if secondary_count > 0:
                failure_msg += f" - Secondary: {', '.join(secondary_confluence)}"
            reasons.append(failure_msg)
            return ConditionCheckResult(
                passed=False,
                pre_trade_passed=True,
                location_passed=True,
                primary_triggers=primary_count,
                secondary_confluence=secondary_count,
                confluence_score=0.0,
                is_aplus_setup=False,
                reasons=reasons,
                details=details
            )
        
        # 4️⃣ Confluence Score
        confluence_score = self._calculate_confluence_score(
            symbol, candles, current_price, vwap, atr1, location_result, signal_result
        )
        details['confluence'] = {
            'score': confluence_score,
            'min_for_trade': self._get_min_score(symbol),
            'min_for_aplus': self._get_min_score_aplus(symbol)
        }
        
        min_score = self._get_min_score(symbol)
        min_score_aplus = self._get_min_score_aplus(symbol)
        
        if confluence_score < min_score:
            reasons.append(f"Confluence score {confluence_score:.1f} < minimum {min_score}")
            return ConditionCheckResult(
                passed=False,
                pre_trade_passed=True,
                location_passed=True,
                primary_triggers=primary_count,
                secondary_confluence=secondary_count,
                confluence_score=confluence_score,
                is_aplus_setup=False,
                reasons=reasons,
                details=details
            )
        
        # All checks passed
        is_aplus = confluence_score >= min_score_aplus
        if is_aplus:
            reasons.append(f"A+ setup: Score {confluence_score:.1f} >= {min_score_aplus}")
        else:
            reasons.append(f"Trade allowed: Score {confluence_score:.1f} >= {min_score}")
        
        return ConditionCheckResult(
            passed=True,
            pre_trade_passed=True,
            location_passed=True,
            primary_triggers=primary_count,
            secondary_confluence=secondary_count,
            confluence_score=confluence_score,
            is_aplus_setup=is_aplus,
            reasons=reasons,
            details=details
        )
    
    def _check_pre_trade_filters(self, symbol: str, candles: List[Dict[str, Any]],
                                spread_data: Optional[SpreadData], current_price: float) -> VolatilityFilterResult:
        """Check pre-trade filters (volatility and spread)"""
        current_spread = spread_data.current_spread if spread_data else 0.0
        
        return self.volatility_filter.check_volatility_filters(
            symbol, candles, current_spread, 
            spread_data.__dict__ if spread_data else None
        )
    
    def _check_location_filter(self, symbol: str, candles: List[Dict[str, Any]],
                              current_price: float, vwap: float, atr1: Optional[float]) -> Dict[str, Any]:
        """Check location filter (must be at "EDGE")"""
        symbol_key = symbol.lower().rstrip('c')
        rules_key = f"{symbol_key}_rules"
        rules = self.config.get(rules_key, {})
        location_config = rules.get('location_filter', {})
        
        edges_detected = []
        
        # Check VWAP band
        if location_config.get('vwap_band_enabled', True):
            vwap_proximity = self.vwap_filter.is_price_near_vwap(current_price, vwap, atr1)
            if vwap_proximity.in_band:
                edges_detected.append('VWAP_BAND')
        
        # Check prior session high/low (if session manager available)
        if location_config.get('prior_session_high_low_enabled', True) and self.session_manager:
            # TODO: Get session high/low from session manager
            # For now, skip this check
            pass
        
        # Check intraday range high/low
        if location_config.get('intraday_range_high_low_enabled', True) and len(candles) >= 20:
            intraday_high = max(c.get('high', 0) for c in candles[-20:])
            intraday_low = min(c.get('low', 0) for c in candles[-20:])
            
            # Check if price is near intraday high/low
            price_pct_from_high = abs(current_price - intraday_high) / intraday_high if intraday_high > 0 else 1.0
            price_pct_from_low = abs(current_price - intraday_low) / intraday_low if intraday_low > 0 else 1.0
            
            if price_pct_from_high < 0.001 or price_pct_from_low < 0.001:  # Within 0.1%
                edges_detected.append('INTRADAY_RANGE')
        
        # Check clean M1/M5 OB zone
        if location_config.get('clean_ob_zone_enabled', True) and len(candles) >= 3:
            micro_obs = self.ob_detector.detect_micro_obs(candles, atr1, current_price)
            if micro_obs:
                # Check if price is near any OB
                for ob in micro_obs:
                    ob_low, ob_high = ob.price_range
                    if ob_low <= current_price <= ob_high:
                        edges_detected.append('OB_ZONE')
                        break
        
        # Check liquidity cluster (equal highs/lows, PDH/PDL)
        if location_config.get('liquidity_cluster_enabled', True) and self.m1_analyzer:
            try:
                # Ensure sufficient candles before analysis (analyzer requires >= 10)
                if candles and len(candles) >= 10:
                    analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
                    liquidity_zones = analysis.get('liquidity_zones', {})
                    
                    # Check for equal highs/lows
                    if liquidity_zones.get('equal_highs_detected') or liquidity_zones.get('equal_lows_detected'):
                        edges_detected.append('LIQUIDITY_CLUSTER')
                else:
                    logger.debug(f"Insufficient candles for liquidity cluster check: {len(candles) if candles else 0}")
            except Exception as e:
                logger.debug(f"Error checking liquidity clusters: {e}")
        
        passed = len(edges_detected) >= 1
        
        return {
            'passed': passed,
            'edges_detected': edges_detected,
            'edge_count': len(edges_detected)
        }
    
    def _check_candle_signals(self, symbol: str, candles: List[Dict[str, Any]],
                             current_price: float, vwap: float, atr1: Optional[float],
                             btc_order_flow: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Check candle signal checklist (primary triggers + secondary confluence)"""
        symbol_key = symbol.lower().rstrip('c')
        rules_key = f"{symbol_key}_rules"
        rules = self.config.get(rules_key, {})
        signals_config = rules.get('candle_signals', {})
        primary_config = signals_config.get('primary_triggers', {})
        secondary_config = signals_config.get('secondary_confluence', {})
        
        primary_triggers = []
        secondary_confluence = []
        
        if len(candles) == 0:
            return {
                'primary_count': 0,
                'secondary_count': 0,
                'primary_triggers': [],
                'secondary_confluence': []
            }
        
        last_candle = candles[-1]
        
        # Primary Triggers
        # 1. Long wick trap
        if primary_config.get('long_wick_trap_enabled', True):
            if self._check_long_wick_trap(last_candle):
                primary_triggers.append('LONG_WICK_TRAP')
        
        # 2. Micro liquidity sweep
        if primary_config.get('micro_liquidity_sweep_enabled', True):
            sweep_result = self.sweep_detector.detect_micro_sweep(candles, atr1)
            if sweep_result.sweep_detected:
                primary_triggers.append('MICRO_LIQUIDITY_SWEEP')
        
        # 3. VWAP tap + rejection
        if primary_config.get('vwap_tap_rejection_enabled', True) and vwap > 0:
            vwap_band = self.vwap_filter.calculate_vwap_band(vwap, current_price, atr1)
            retest_result = self.vwap_filter.detect_vwap_retest(candles, vwap, vwap_band, symbol)
            if retest_result.retest_detected and retest_result.retest_type == "WICK_REJECTION":
                primary_triggers.append('VWAP_TAP_REJECTION')
        
        # 4. Strong engulfing candle
        if primary_config.get('strong_engulfing_enabled', True) and len(candles) >= 2:
            if self._check_strong_engulfing(candles[-2], last_candle):
                primary_triggers.append('STRONG_ENGULFING')
        
        # Secondary Confluence
        # 1. OB retest
        if secondary_config.get('ob_retest_enabled', True) and len(candles) >= 3:
            micro_obs = self.ob_detector.detect_micro_obs(candles, atr1, current_price)
            for ob in micro_obs:
                if ob.retest_detected:
                    secondary_confluence.append('OB_RETEST')
                    break
        
        # 2. Fresh micro-CHOCH on M1
        if secondary_config.get('fresh_micro_choch_enabled', True) and self.m1_analyzer:
            try:
                # Ensure sufficient candles before analysis (analyzer requires >= 10)
                if candles and len(candles) >= 10:
                    analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
                    structure = analysis.get('structure', {})
                    if structure.get('choch_detected') and structure.get('choch_bars_ago', 10) <= 5:
                        secondary_confluence.append('FRESH_MICRO_CHOCH')
                else:
                    logger.debug(f"Insufficient candles for micro-CHOCH check: {len(candles) if candles else 0}")
            except Exception as e:
                logger.debug(f"Error checking micro-CHOCH: {e}")
        
        # 3. Strong session momentum
        if secondary_config.get('strong_session_momentum_enabled', True):
            if self._check_session_momentum(symbol):
                secondary_confluence.append('SESSION_MOMENTUM')
        
        # 4. Increasing volume
        if secondary_config.get('increasing_volume_enabled', True) and len(candles) >= 3:
            if self._check_increasing_volume(candles[-3:]):
                secondary_confluence.append('INCREASING_VOLUME')
        
        # BTC-specific: CVD divergence (if available)
        if symbol.upper().startswith('BTC') and btc_order_flow:
            cvd_divergence = btc_order_flow.get('cvd_divergence', {})
            if cvd_divergence.get('detected', False):
                secondary_confluence.append('CVD_DIVERGENCE')
        
        return {
            'primary_count': len(primary_triggers),
            'secondary_count': len(secondary_confluence),
            'primary_triggers': primary_triggers,
            'secondary_confluence': secondary_confluence
        }
    
    def _calculate_confluence_score(self, symbol: str, candles: List[Dict[str, Any]],
                                   current_price: float, vwap: float, atr1: Optional[float],
                                   location_result: Dict[str, Any],
                                   signal_result: Dict[str, Any]) -> float:
        """Calculate confluence score (0-8 points)"""
        symbol_key = symbol.lower().rstrip('c')
        rules_key = f"{symbol_key}_rules"
        rules = self.config.get(rules_key, {})
        scoring_config = rules.get('confluence_scoring', {})
        
        scores = {}
        
        # Wick quality (0-2)
        if len(candles) > 0:
            scores['wick_quality'] = self._score_wick_quality(candles[-1], scoring_config.get('wick_quality_points', 2))
        else:
            scores['wick_quality'] = 0.0
        
        # VWAP proximity (0-2)
        if vwap > 0:
            vwap_proximity = self.vwap_filter.is_price_near_vwap(current_price, vwap, atr1)
            scores['vwap_proximity'] = self._score_vwap_proximity(vwap_proximity, scoring_config.get('vwap_proximity_points', 2))
        else:
            scores['vwap_proximity'] = 0.0
        
        # Edge location (0-2)
        edge_count = location_result.get('edge_count', 0)
        scores['edge_location'] = self._score_edge_location(edge_count, scoring_config.get('edge_location_points', 2))
        
        # Volatility state (0-1)
        if len(candles) >= 5:
            expanding = self.volatility_filter.is_volatility_expanding(candles)
            scores['volatility_state'] = 1.0 if expanding else 0.0
        else:
            scores['volatility_state'] = 0.0
        
        # Session quality (0-1)
        scores['session_quality'] = self._score_session_quality(symbol, scoring_config.get('session_quality_points', 1))
        
        # Sum scores (with normalization to prevent bias)
        total = sum(scores.values())
        
        # Cap at maximum (8 points)
        return min(8.0, total)
    
    def _check_long_wick_trap(self, candle: Dict[str, Any]) -> bool:
        """Check for long wick trap (wick ≥ 1.5-2× body)"""
        open_price = candle.get('open', 0)
        close = candle.get('close', 0)
        high = candle.get('high', 0)
        low = candle.get('low', 0)
        
        body_size = abs(close - open_price)
        if body_size == 0:
            return False
        
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        
        # Check if wick is ≥ 1.5× body
        return (upper_wick >= body_size * 1.5) or (lower_wick >= body_size * 1.5)
    
    def _check_strong_engulfing(self, prev_candle: Dict[str, Any], curr_candle: Dict[str, Any]) -> bool:
        """Check for strong engulfing candle"""
        prev_open = prev_candle.get('open', 0)
        prev_close = prev_candle.get('close', 0)
        curr_open = curr_candle.get('open', 0)
        curr_close = curr_candle.get('close', 0)
        
        # Bullish engulfing
        if prev_close < prev_open and curr_close > curr_open:
            if curr_open < prev_close and curr_close > prev_open:
                return True
        
        # Bearish engulfing
        if prev_close > prev_open and curr_close < curr_open:
            if curr_open > prev_close and curr_close < prev_open:
                return True
        
        return False
    
    def _check_session_momentum(self, symbol: str) -> bool:
        """Check for strong session momentum (London/NY push)"""
        if not self.session_manager:
            return False
        
        try:
            from infra.session_helpers import SessionHelpers
            current_session = SessionHelpers.get_current_session()
            
            # Strong momentum in London/NY/Overlap sessions
            return current_session in ['LONDON', 'NY', 'OVERLAP']
        except Exception:
            return False
    
    def _check_increasing_volume(self, recent_candles: List[Dict[str, Any]]) -> bool:
        """Check if volume is increasing"""
        if len(recent_candles) < 2:
            return False
        
        volumes = [c.get('volume', 0) for c in recent_candles if 'volume' in c]
        if len(volumes) < 2:
            return False
        
        # Check if last volume is higher than previous
        return volumes[-1] > volumes[-2] * 1.2  # 20% increase
    
    def _score_wick_quality(self, candle: Dict[str, Any], max_points: float) -> float:
        """Score wick quality (0-max_points)"""
        open_price = candle.get('open', 0)
        close = candle.get('close', 0)
        high = candle.get('high', 0)
        low = candle.get('low', 0)
        
        body_size = abs(close - open_price)
        if body_size == 0:
            return 0.0
        
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        max_wick = max(upper_wick, lower_wick)
        
        wick_ratio = max_wick / body_size
        
        if wick_ratio >= 2.0:
            return max_points  # 2 points
        elif wick_ratio >= 1.5:
            return max_points * 0.5  # 1 point
        else:
            return 0.0
    
    def _score_vwap_proximity(self, vwap_proximity: VWAPProximityResult, max_points: float) -> float:
        """Score VWAP proximity (0-max_points)"""
        if not vwap_proximity.is_near_vwap:
            return 0.0
        
        distance_pct = vwap_proximity.distance_pct
        
        if distance_pct < 0.0005:  # < 0.05%
            return max_points  # 2 points
        elif distance_pct < 0.001:  # < 0.1%
            return max_points * 0.5  # 1 point
        else:
            return 0.0
    
    def _score_edge_location(self, edge_count: int, max_points: float) -> float:
        """Score edge location (0-max_points)"""
        if edge_count == 0:
            return 0.0
        elif edge_count == 1:
            return max_points * 0.5  # 1 point
        else:
            return max_points  # 2 points (multiple edges)
    
    def _score_session_quality(self, symbol: str, max_points: float) -> float:
        """Score session quality (0-max_points)"""
        try:
            from infra.session_helpers import SessionHelpers
            current_session = SessionHelpers.get_current_session()
            
            # Active sessions get full points
            if current_session in ['LONDON', 'NY', 'OVERLAP']:
                return max_points
            else:
                return 0.0
        except Exception:
            return 0.0
    
    def _get_min_score(self, symbol: str) -> float:
        """Get minimum confluence score for trade"""
        symbol_key = symbol.lower().rstrip('c')
        rules_key = f"{symbol_key}_rules"
        rules = self.config.get(rules_key, {})
        scoring_config = rules.get('confluence_scoring', {})
        return scoring_config.get('min_score_for_trade', 5.0)
    
    def _get_min_score_aplus(self, symbol: str) -> float:
        """Get minimum confluence score for A+ setup"""
        symbol_key = symbol.lower().rstrip('c')
        rules_key = f"{symbol_key}_rules"
        rules = self.config.get(rules_key, {})
        scoring_config = rules.get('confluence_scoring', {})
        return scoring_config.get('min_score_for_aplus', 7.0)

