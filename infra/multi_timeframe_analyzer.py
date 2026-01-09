"""
Multi-Timeframe Analyzer - Proper top-down analysis across 5 timeframes
Enhanced with Advanced institutional-grade indicators
"""
import logging
import threading
from typing import Dict, Optional
from datetime import datetime
import pandas as pd
from domain.market_structure import _symmetric_swings, label_swings, detect_bos_choch

logger = logging.getLogger(__name__)

# Dynamic volatility-based timeframe weights
# Adjusts weights based on market volatility regime
VOLATILITY_WEIGHTS = {
    "low": {  # Range market
        "H4": 0.30,
        "H1": 0.25,
        "M30": 0.20,
        "M15": 0.15,
        "M5": 0.10
    },
    "medium": {  # Normal conditions
        "H4": 0.40,
        "H1": 0.25,
        "M30": 0.15,
        "M15": 0.12,
        "M5": 0.08
    },
    "high": {  # Expansion/volatile (FOMC, BTC spikes)
        "H4": 0.50,
        "H1": 0.30,
        "M30": 0.12,
        "M15": 0.06,
        "M5": 0.02
    }
}


class MultiTimeframeAnalyzer:
    """
    Analyze symbol across M5, M15, M30, H1, H4 using proper top-down methodology
    Enhanced with V8 Advanced Technical Features
    
    Hierarchy:
    H4 = Macro Tide (overall bias)
    H1 = Swing Context (structure zones)
    M30 = Setup Frame (structure breaks)
    M15 = Trigger Frame (entry signals)
    M5 = Execution Frame (precise entry/exit)
    
    V8 Enhancement:
    - Integrates RMAG, EMA Slope, Bollinger-ADX, Pressure Ratio, MTF Alignment
    - Uses Advanced features for confidence adjustments
    - Provides institutional-grade market structure analysis
    """
    
    def __init__(self, indicator_bridge, mt5_service=None):
        self.indicator_bridge = indicator_bridge
        self.mt5_service = mt5_service
        self.advanced_features = None
        
        # Trend memory buffer for stabilizing bias (rolling 3-bar memory per timeframe)
        self.trend_memory = {
            "H4": [],
            "H1": [],
            "M30": [],
            "M15": [],
            "M5": []
        }
        # Thread safety lock for trend memory (if analyze() called concurrently)
        self.trend_memory_lock = threading.Lock()
    
    def analyze(self, symbol: str) -> Dict:
        """
        Perform complete multi-timeframe analysis with V8 enhancement
        
        Returns comprehensive analysis with:
        - H4 bias (trend direction)
        - H1 momentum (continuation/pullback)
        - M30 setup (structure confirmation)
        - M15 trigger (entry signal)
        - M5 execution (precise timing)
        - Overall confluence score
        - Trade recommendation
        - V8 advanced indicators and insights
        """
        try:
            # Get all timeframe data
            multi_data = self.indicator_bridge.get_multi(symbol)
            
            if not multi_data:
                return self._empty_result(symbol)
            
            # Fetch Advanced features for advanced analysis
            self.advanced_features = self._fetch_advanced_features(symbol)
            
            # Analyze each timeframe (now Advanced-enhanced)
            h4_analysis = self._analyze_h4_bias(multi_data.get("H4", {}), symbol)
            h1_analysis = self._analyze_h1_context(multi_data.get("H1", {}), h4_analysis, symbol)
            m30_analysis = self._analyze_m30_setup(multi_data.get("M30", {}), h1_analysis, symbol)
            m15_analysis = self._analyze_m15_trigger(multi_data.get("M15", {}), m30_analysis, symbol)
            m5_analysis = self._analyze_m5_execution(multi_data.get("M5", {}), m15_analysis, symbol)
            
            # Calculate alignment score (Advanced-enhanced)
            alignment_score = self._calculate_alignment(
                h4_analysis, h1_analysis, m30_analysis, m15_analysis, m5_analysis
            )
            
            # Generate recommendation (Advanced-enhanced)
            recommendation = self._generate_recommendation(
                h4_analysis, h1_analysis, m30_analysis, m15_analysis, m5_analysis, alignment_score
            )
            
            # Build result with Advanced insights
            result = {
                "symbol": symbol,
                "timestamp": datetime.utcnow().isoformat(),
                "timeframes": {
                    "H4": h4_analysis,
                    "H1": h1_analysis,
                    "M30": m30_analysis,
                    "M15": m15_analysis,
                    "M5": m5_analysis
                },
                "alignment_score": alignment_score,
                "recommendation": recommendation
            }
            
            # Add Advanced insights if available
            if self.advanced_features:
                result["advanced_insights"] = self._generate_advanced_insights()
                result["advanced_summary"] = self._generate_advanced_summary()
            
            return result
            
        except Exception as e:
            logger.error(f"Multi-timeframe analysis error for {symbol}: {e}", exc_info=True)
            return self._empty_result(symbol)
    
    def _analyze_h4_bias(self, h4_data: Dict, symbol: str) -> Dict:
        """
        H4 = Macro Tide
        Determines overall trend bias and direction
        """
        if not h4_data:
            return {"bias": "UNKNOWN", "confidence": 0, "reason": "No H4 data"}
        
        # Initialize CHOCH/BOS defaults
        choch_detected = False
        choch_bull = False
        choch_bear = False
        bos_detected = False
        bos_bull = False
        bos_bear = False
        
        try:
            # ⚠️ CRITICAL: Check if h4_data is not None before accessing .get()
            if h4_data:
                opens = h4_data.get("opens", []) or []
                highs = h4_data.get("highs", []) or []
                lows = h4_data.get("lows", []) or []
                closes = h4_data.get("closes", []) or []
                
                # Ensure all are lists (handle None case)
                if not isinstance(opens, list):
                    opens = []
                if not isinstance(highs, list):
                    highs = []
                if not isinstance(lows, list):
                    lows = []
                if not isinstance(closes, list):
                    closes = []
                
                if len(closes) >= 10:
                    # Get actual timestamps if available, otherwise use index
                    times = h4_data.get("times", [])
                    if times and len(times) == len(closes):
                        try:
                            # Handle different time formats: Unix timestamps (int/float) or ISO strings
                            first_time = times[0] if times else None
                            if first_time is not None:
                                if isinstance(first_time, (int, float)):
                                    # Unix timestamp - check if seconds or milliseconds
                                    if first_time > 1e10:  # Likely milliseconds
                                        times_series = pd.to_datetime(times, unit='ms', errors='coerce')
                                    else:  # Likely seconds
                                        times_series = pd.to_datetime(times, unit='s', errors='coerce')
                                else:
                                    # String or datetime - use errors='coerce' to suppress warnings and handle parsing errors
                                    times_series = pd.to_datetime(times, errors='coerce')
                            else:
                                times_series = pd.to_datetime(times, errors='coerce')
                            times = (times_series.astype('int64') // 10**9).tolist()
                        except Exception:
                            times = list(range(len(closes)))
                    else:
                        times = list(range(len(closes)))
                    
                    # Convert lists to DataFrame for _symmetric_swings
                    bars_df = pd.DataFrame({
                        "open": opens,
                        "high": highs,
                        "low": lows,
                        "close": closes,
                        "time": times
                    })
                    
                    # Get swings
                    raw_swings = _symmetric_swings(bars_df, left=3, right=3, lookback=20)
                    
                    if raw_swings:
                        labeled_swings = label_swings(raw_swings)
                        
                        if labeled_swings:
                            # Convert StructurePoint objects to dicts for detect_bos_choch
                            swings_dict = [{"price": s.price, "kind": s.kind} for s in labeled_swings]
                            
                            # Get current close
                            current_close = float(closes[-1]) if closes else float(h4_data.get("current_close", 0))
                            
                            # Get ATR - check 'atr14' first (standard field name), then 'atr' for compatibility
                            atr = float(h4_data.get("atr14", 0)) or float(h4_data.get("atr", 0))
                            if atr <= 0:
                                if len(closes) < 2:
                                    atr = 1.0
                                elif len(highs) >= 14 and len(lows) >= 14 and len(closes) >= 15:
                                    true_ranges = []
                                    for i in range(1, min(15, len(closes))):
                                        tr = max(
                                            highs[i] - lows[i],
                                            abs(highs[i] - closes[i-1]),
                                            abs(lows[i] - closes[i-1])
                                        )
                                        true_ranges.append(tr)
                                    atr = sum(true_ranges) / len(true_ranges) if true_ranges else 1.0
                                elif len(highs) >= 14 and len(lows) >= 14:
                                    recent_highs = highs[-14:]
                                    recent_lows = lows[-14:]
                                    if recent_highs and recent_lows:
                                        atr = (max(recent_highs) - min(recent_lows)) / 14
                                    else:
                                        atr = 1.0
                                else:
                                    atr = 1.0
                            
                            # Detect CHOCH/BOS using detect_bos_choch() directly
                            choch_bos_result = detect_bos_choch(swings_dict, current_close, atr)
                            
                            if choch_bos_result:
                                choch_bull = choch_bos_result.get("choch_bull", False)
                                choch_bear = choch_bos_result.get("choch_bear", False)
                                bos_bull = choch_bos_result.get("bos_bull", False)
                                bos_bear = choch_bos_result.get("bos_bear", False)
                                choch_detected = choch_bull or choch_bear
                                bos_detected = bos_bull or bos_bear
                                
                                if choch_detected or bos_detected:
                                    logger.debug(f"CHOCH/BOS detected for {symbol} H4: choch={choch_detected}, bos={bos_detected}")
        except Exception as e:
            logger.debug(f"CHOCH/BOS detection failed for {symbol} H4: {e}")
        
        ema20 = float(h4_data.get("ema20", 0))
        ema50 = float(h4_data.get("ema50", 0))
        ema200 = float(h4_data.get("ema200", 0))
        adx = float(h4_data.get("adx", 0))
        rsi = float(h4_data.get("rsi", 50))
        
        # Get current close
        close_data = h4_data.get("close", 0)
        if isinstance(close_data, list):
            close = float(close_data[-1]) if close_data else 0.0
        else:
            close = float(close_data) if close_data else 0.0
        close = float(h4_data.get("current_close", close))
        
        # Determine bias
        bias = "NEUTRAL"
        confidence = 50
        reason = ""
        
        if close > ema20 > ema50 > ema200:
            bias = "BULLISH"
            confidence = 85 if adx > 25 else 70
            reason = "Strong bullish alignment: Price > EMA20 > EMA50 > EMA200"
            if adx > 25:
                reason += f" | Strong trend (ADX={adx:.1f})"
        elif close < ema20 < ema50 < ema200:
            bias = "BEARISH"
            confidence = 85 if adx > 25 else 70
            reason = "Strong bearish alignment: Price < EMA20 < EMA50 < EMA200"
            if adx > 25:
                reason += f" | Strong trend (ADX={adx:.1f})"
        elif close > ema20 > ema50:
            bias = "BULLISH"
            confidence = 65
            reason = "Moderate bullish: Price > EMA20 > EMA50"
        elif close < ema20 < ema50:
            bias = "BEARISH"
            confidence = 65
            reason = "Moderate bearish: Price < EMA20 < EMA50"
        else:
            bias = "NEUTRAL"
            confidence = 40
            reason = "No clear EMA alignment - choppy or transitioning"
        
        return {
            "bias": bias,
            "confidence": confidence,
            "reason": reason,
            "adx": adx,
            "rsi": rsi,
            "ema_stack": f"EMA20={ema20:.2f}, EMA50={ema50:.2f}, EMA200={ema200:.2f}",
            "verdict": f"H4 Bias: {bias} ({confidence}% confidence)",
            "choch_detected": choch_detected,
            "choch_bull": choch_bull,
            "choch_bear": choch_bear,
            "bos_detected": bos_detected,
            "bos_bull": bos_bull,
            "bos_bear": bos_bear
        }
    
    def _analyze_h1_context(self, h1_data: Dict, h4_analysis: Dict, symbol: str) -> Dict:
        """
        H1 = Swing Context
        Confirms momentum and identifies structure zones
        """
        if not h1_data:
            return {"status": "UNKNOWN", "confidence": 0, "reason": "No H1 data"}
        
        # Initialize CHOCH/BOS defaults
        choch_detected = False
        choch_bull = False
        choch_bear = False
        bos_detected = False
        bos_bull = False
        bos_bear = False
        
        try:
            if h1_data:
                opens = h1_data.get("opens", []) or []
                highs = h1_data.get("highs", []) or []
                lows = h1_data.get("lows", []) or []
                closes = h1_data.get("closes", []) or []
                
                if not isinstance(opens, list):
                    opens = []
                if not isinstance(highs, list):
                    highs = []
                if not isinstance(lows, list):
                    lows = []
                if not isinstance(closes, list):
                    closes = []
                
                if len(closes) >= 10:
                    times = h1_data.get("times", [])
                    if times and len(times) == len(closes):
                        try:
                            # Handle different time formats: Unix timestamps (int/float) or ISO strings
                            first_time = times[0] if times else None
                            if first_time is not None:
                                if isinstance(first_time, (int, float)):
                                    # Unix timestamp - check if seconds or milliseconds
                                    if first_time > 1e10:  # Likely milliseconds
                                        times_series = pd.to_datetime(times, unit='ms', errors='coerce')
                                    else:  # Likely seconds
                                        times_series = pd.to_datetime(times, unit='s', errors='coerce')
                                else:
                                    # String or datetime - use errors='coerce' to suppress warnings and handle parsing errors
                                    times_series = pd.to_datetime(times, errors='coerce')
                            else:
                                times_series = pd.to_datetime(times, errors='coerce')
                            times = (times_series.astype('int64') // 10**9).tolist()
                        except Exception:
                            times = list(range(len(closes)))
                    else:
                        times = list(range(len(closes)))
                    
                    bars_df = pd.DataFrame({
                        "open": opens,
                        "high": highs,
                        "low": lows,
                        "close": closes,
                        "time": times
                    })
                    
                    raw_swings = _symmetric_swings(bars_df, left=3, right=3, lookback=20)
                    
                    if raw_swings:
                        labeled_swings = label_swings(raw_swings)
                        
                        if labeled_swings:
                            swings_dict = [{"price": s.price, "kind": s.kind} for s in labeled_swings]
                            
                            current_close = float(closes[-1]) if closes else float(h1_data.get("current_close", 0))
                            
                            atr = float(h1_data.get("atr14", 0)) or float(h1_data.get("atr", 0))
                            if atr <= 0:
                                if len(closes) < 2:
                                    atr = 1.0
                                elif len(highs) >= 14 and len(lows) >= 14 and len(closes) >= 15:
                                    true_ranges = []
                                    for i in range(1, min(15, len(closes))):
                                        tr = max(
                                            highs[i] - lows[i],
                                            abs(highs[i] - closes[i-1]),
                                            abs(lows[i] - closes[i-1])
                                        )
                                        true_ranges.append(tr)
                                    atr = sum(true_ranges) / len(true_ranges) if true_ranges else 1.0
                                elif len(highs) >= 14 and len(lows) >= 14:
                                    recent_highs = highs[-14:]
                                    recent_lows = lows[-14:]
                                    if recent_highs and recent_lows:
                                        atr = (max(recent_highs) - min(recent_lows)) / 14
                                    else:
                                        atr = 1.0
                                else:
                                    atr = 1.0
                            
                            choch_bos_result = detect_bos_choch(swings_dict, current_close, atr)
                            
                            if choch_bos_result:
                                choch_bull = choch_bos_result.get("choch_bull", False)
                                choch_bear = choch_bos_result.get("choch_bear", False)
                                bos_bull = choch_bos_result.get("bos_bull", False)
                                bos_bear = choch_bos_result.get("bos_bear", False)
                                choch_detected = choch_bull or choch_bear
                                bos_detected = bos_bull or bos_bear
                                
                                if choch_detected or bos_detected:
                                    logger.debug(f"CHOCH/BOS detected for {symbol} H1: choch={choch_detected}, bos={bos_detected}")
        except Exception as e:
            logger.debug(f"CHOCH/BOS detection failed for {symbol} H1: {e}")
        
        ema20 = float(h1_data.get("ema20", 0))
        ema50 = float(h1_data.get("ema50", 0))
        rsi = float(h1_data.get("rsi", 50))
        macd = float(h1_data.get("macd", 0))
        macd_signal = float(h1_data.get("macd_signal", 0))
        
        close_data = h1_data.get("close", 0)
        if isinstance(close_data, list):
            close = float(close_data[-1]) if close_data else 0.0
        else:
            close = float(close_data) if close_data else 0.0
        close = float(h1_data.get("current_close", close))
        
        h4_bias = h4_analysis.get("bias", "NEUTRAL")
        
        # Determine H1 status
        status = "NEUTRAL"
        confidence = 50
        reason = ""
        
        # Check if H1 aligns with H4
        if h4_bias == "BULLISH":
            if close > ema20 and rsi > 50:
                status = "CONTINUATION"
                confidence = 80
                reason = "H1 confirms H4 bullish bias - price above EMA20, RSI > 50"
            elif close < ema20 and 40 <= rsi <= 60:
                status = "PULLBACK"
                confidence = 75
                reason = "Healthy pullback in H4 uptrend - potential buy opportunity"
            else:
                status = "DIVERGENCE"
                confidence = 40
                reason = "H1 not aligned with H4 bullish bias - caution"
        
        elif h4_bias == "BEARISH":
            if close < ema20 and rsi < 50:
                status = "CONTINUATION"
                confidence = 80
                reason = "H1 confirms H4 bearish bias - price below EMA20, RSI < 50"
            elif close > ema20 and 40 <= rsi <= 60:
                status = "PULLBACK"
                confidence = 75
                reason = "Healthy pullback in H4 downtrend - potential sell opportunity"
            else:
                status = "DIVERGENCE"
                confidence = 40
                reason = "H1 not aligned with H4 bearish bias - caution"
        
        else:
            status = "RANGING"
            confidence = 50
            reason = "H4 neutral - H1 showing range-bound behavior"
        
        return {
            "status": status,
            "confidence": confidence,
            "reason": reason,
            "rsi": rsi,
            "macd_cross": "bullish" if macd > macd_signal else "bearish",
            "price_vs_ema20": "above" if close > ema20 else "below",
            "verdict": f"H1 Context: {status} ({confidence}% confidence)",
            "choch_detected": choch_detected,
            "choch_bull": choch_bull,
            "choch_bear": choch_bear,
            "bos_detected": bos_detected,
            "bos_bull": bos_bull,
            "bos_bear": bos_bear
        }
    
    def _analyze_m30_setup(self, m30_data: Dict, h1_analysis: Dict, symbol: str) -> Dict:
        """
        M30 = Setup Frame
        Validates structure breaks and pattern formation
        """
        if not m30_data:
            return {"setup": "NONE", "confidence": 0, "reason": "No M30 data"}
        
        # Initialize CHOCH/BOS defaults
        choch_detected = False
        choch_bull = False
        choch_bear = False
        bos_detected = False
        bos_bull = False
        bos_bear = False
        
        try:
            if m30_data:
                opens = m30_data.get("opens", []) or []
                highs = m30_data.get("highs", []) or []
                lows = m30_data.get("lows", []) or []
                closes = m30_data.get("closes", []) or []
                
                if not isinstance(opens, list):
                    opens = []
                if not isinstance(highs, list):
                    highs = []
                if not isinstance(lows, list):
                    lows = []
                if not isinstance(closes, list):
                    closes = []
                
                if len(closes) >= 10:
                    times = m30_data.get("times", [])
                    if times and len(times) == len(closes):
                        try:
                            # Handle different time formats: Unix timestamps (int/float) or ISO strings
                            first_time = times[0] if times else None
                            if first_time is not None:
                                if isinstance(first_time, (int, float)):
                                    # Unix timestamp - check if seconds or milliseconds
                                    if first_time > 1e10:  # Likely milliseconds
                                        times_series = pd.to_datetime(times, unit='ms', errors='coerce')
                                    else:  # Likely seconds
                                        times_series = pd.to_datetime(times, unit='s', errors='coerce')
                                else:
                                    # String or datetime - use errors='coerce' to suppress warnings and handle parsing errors
                                    times_series = pd.to_datetime(times, errors='coerce')
                            else:
                                times_series = pd.to_datetime(times, errors='coerce')
                            times = (times_series.astype('int64') // 10**9).tolist()
                        except Exception:
                            times = list(range(len(closes)))
                    else:
                        times = list(range(len(closes)))
                    
                    bars_df = pd.DataFrame({
                        "open": opens,
                        "high": highs,
                        "low": lows,
                        "close": closes,
                        "time": times
                    })
                    
                    raw_swings = _symmetric_swings(bars_df, left=3, right=3, lookback=20)
                    
                    if raw_swings:
                        labeled_swings = label_swings(raw_swings)
                        
                        if labeled_swings:
                            swings_dict = [{"price": s.price, "kind": s.kind} for s in labeled_swings]
                            
                            current_close = float(closes[-1]) if closes else float(m30_data.get("current_close", 0))
                            
                            atr = float(m30_data.get("atr14", 0)) or float(m30_data.get("atr", 0))
                            if atr <= 0:
                                if len(closes) < 2:
                                    atr = 1.0
                                elif len(highs) >= 14 and len(lows) >= 14 and len(closes) >= 15:
                                    true_ranges = []
                                    for i in range(1, min(15, len(closes))):
                                        tr = max(
                                            highs[i] - lows[i],
                                            abs(highs[i] - closes[i-1]),
                                            abs(lows[i] - closes[i-1])
                                        )
                                        true_ranges.append(tr)
                                    atr = sum(true_ranges) / len(true_ranges) if true_ranges else 1.0
                                elif len(highs) >= 14 and len(lows) >= 14:
                                    recent_highs = highs[-14:]
                                    recent_lows = lows[-14:]
                                    if recent_highs and recent_lows:
                                        atr = (max(recent_highs) - min(recent_lows)) / 14
                                    else:
                                        atr = 1.0
                                else:
                                    atr = 1.0
                            
                            choch_bos_result = detect_bos_choch(swings_dict, current_close, atr)
                            
                            if choch_bos_result:
                                choch_bull = choch_bos_result.get("choch_bull", False)
                                choch_bear = choch_bos_result.get("choch_bear", False)
                                bos_bull = choch_bos_result.get("bos_bull", False)
                                bos_bear = choch_bos_result.get("bos_bear", False)
                                choch_detected = choch_bull or choch_bear
                                bos_detected = bos_bull or bos_bear
                                
                                if choch_detected or bos_detected:
                                    logger.debug(f"CHOCH/BOS detected for {symbol} M30: choch={choch_detected}, bos={bos_detected}")
        except Exception as e:
            logger.debug(f"CHOCH/BOS detection failed for {symbol} M30: {e}")
        
        rsi = float(m30_data.get("rsi", 50))
        ema20 = float(m30_data.get("ema20", 0))
        ema50 = float(m30_data.get("ema50", 0))
        atr = float(m30_data.get("atr14", 0))
        
        close_data = m30_data.get("close", 0)
        if isinstance(close_data, list):
            close = float(close_data[-1]) if close_data else 0.0
        else:
            close = float(close_data) if close_data else 0.0
        close = float(m30_data.get("current_close", close))
        
        h1_status = h1_analysis.get("status", "NEUTRAL")
        
        # Determine M30 setup
        setup = "NONE"
        confidence = 50
        reason = ""
        
        if h1_status == "CONTINUATION":
            if close > ema20 > ema50 and rsi > 55:
                setup = "BUY_SETUP"
                confidence = 80
                reason = "M30 confirms continuation - bullish structure intact"
            elif close < ema20 < ema50 and rsi < 45:
                setup = "SELL_SETUP"
                confidence = 80
                reason = "M30 confirms continuation - bearish structure intact"
        
        elif h1_status == "PULLBACK":
            if close > ema50 and 40 <= rsi <= 50:
                setup = "BUY_SETUP"
                confidence = 75
                reason = "M30 shows pullback ending - RSI near support, price above EMA50"
            elif close < ema50 and 50 <= rsi <= 60:
                setup = "SELL_SETUP"
                confidence = 75
                reason = "M30 shows pullback ending - RSI near resistance, price below EMA50"
        
        else:
            setup = "WAIT"
            confidence = 30
            reason = "M30 structure unclear - wait for better setup"
        
        return {
            "setup": setup,
            "confidence": confidence,
            "reason": reason,
            "rsi": rsi,
            "atr": atr,
            "ema_alignment": "bullish" if ema20 > ema50 else "bearish" if ema20 < ema50 else "neutral",
            "verdict": f"M30 Setup: {setup} ({confidence}% confidence)",
            "choch_detected": choch_detected,
            "choch_bull": choch_bull,
            "choch_bear": choch_bear,
            "bos_detected": bos_detected,
            "bos_bull": bos_bull,
            "bos_bear": bos_bear
        }
    
    def _analyze_m15_trigger(self, m15_data: Dict, m30_analysis: Dict, symbol: str) -> Dict:
        """
        M15 = Trigger Frame
        Generates entry signals and confirms patterns
        """
        if not m15_data:
            return {"trigger": "NONE", "confidence": 0, "reason": "No M15 data"}
        
        # Initialize CHOCH/BOS defaults
        choch_detected = False
        choch_bull = False
        choch_bear = False
        bos_detected = False
        bos_bull = False
        bos_bear = False
        
        try:
            if m15_data:
                opens = m15_data.get("opens", []) or []
                highs = m15_data.get("highs", []) or []
                lows = m15_data.get("lows", []) or []
                closes = m15_data.get("closes", []) or []
                
                if not isinstance(opens, list):
                    opens = []
                if not isinstance(highs, list):
                    highs = []
                if not isinstance(lows, list):
                    lows = []
                if not isinstance(closes, list):
                    closes = []
                
                if len(closes) >= 10:
                    times = m15_data.get("times", [])
                    if times and len(times) == len(closes):
                        try:
                            # Handle different time formats: Unix timestamps (int/float) or ISO strings
                            first_time = times[0] if times else None
                            if first_time is not None:
                                if isinstance(first_time, (int, float)):
                                    # Unix timestamp - check if seconds or milliseconds
                                    if first_time > 1e10:  # Likely milliseconds
                                        times_series = pd.to_datetime(times, unit='ms', errors='coerce')
                                    else:  # Likely seconds
                                        times_series = pd.to_datetime(times, unit='s', errors='coerce')
                                else:
                                    # String or datetime - use errors='coerce' to suppress warnings and handle parsing errors
                                    times_series = pd.to_datetime(times, errors='coerce')
                            else:
                                times_series = pd.to_datetime(times, errors='coerce')
                            times = (times_series.astype('int64') // 10**9).tolist()
                        except Exception:
                            times = list(range(len(closes)))
                    else:
                        times = list(range(len(closes)))
                    
                    bars_df = pd.DataFrame({
                        "open": opens,
                        "high": highs,
                        "low": lows,
                        "close": closes,
                        "time": times
                    })
                    
                    raw_swings = _symmetric_swings(bars_df, left=3, right=3, lookback=20)
                    
                    if raw_swings:
                        labeled_swings = label_swings(raw_swings)
                        
                        if labeled_swings:
                            swings_dict = [{"price": s.price, "kind": s.kind} for s in labeled_swings]
                            
                            current_close = float(closes[-1]) if closes else float(m15_data.get("current_close", 0))
                            
                            atr = float(m15_data.get("atr14", 0)) or float(m15_data.get("atr", 0))
                            if atr <= 0:
                                if len(closes) < 2:
                                    atr = 1.0
                                elif len(highs) >= 14 and len(lows) >= 14 and len(closes) >= 15:
                                    true_ranges = []
                                    for i in range(1, min(15, len(closes))):
                                        tr = max(
                                            highs[i] - lows[i],
                                            abs(highs[i] - closes[i-1]),
                                            abs(lows[i] - closes[i-1])
                                        )
                                        true_ranges.append(tr)
                                    atr = sum(true_ranges) / len(true_ranges) if true_ranges else 1.0
                                elif len(highs) >= 14 and len(lows) >= 14:
                                    recent_highs = highs[-14:]
                                    recent_lows = lows[-14:]
                                    if recent_highs and recent_lows:
                                        atr = (max(recent_highs) - min(recent_lows)) / 14
                                    else:
                                        atr = 1.0
                                else:
                                    atr = 1.0
                            
                            choch_bos_result = detect_bos_choch(swings_dict, current_close, atr)
                            
                            if choch_bos_result:
                                choch_bull = choch_bos_result.get("choch_bull", False)
                                choch_bear = choch_bos_result.get("choch_bear", False)
                                bos_bull = choch_bos_result.get("bos_bull", False)
                                bos_bear = choch_bos_result.get("bos_bear", False)
                                choch_detected = choch_bull or choch_bear
                                bos_detected = bos_bull or bos_bear
                                
                                if choch_detected or bos_detected:
                                    logger.debug(f"CHOCH/BOS detected for {symbol} M15: choch={choch_detected}, bos={bos_detected}")
        except Exception as e:
            logger.debug(f"CHOCH/BOS detection failed for {symbol} M15: {e}")
        
        rsi = float(m15_data.get("rsi", 50))
        macd = float(m15_data.get("macd", 0))
        macd_signal = float(m15_data.get("macd_signal", 0))
        ema20 = float(m15_data.get("ema20", 0))
        
        close_data = m15_data.get("close", 0)
        if isinstance(close_data, list):
            close = float(close_data[-1]) if close_data else 0.0
        else:
            close = float(close_data) if close_data else 0.0
        close = float(m15_data.get("current_close", close))
        
        m30_setup = m30_analysis.get("setup", "NONE")
        
        # Determine M15 trigger
        trigger = "NONE"
        confidence = 50
        reason = ""
        
        if m30_setup == "BUY_SETUP":
            if close > ema20 and macd > macd_signal and rsi > 50:
                trigger = "BUY_TRIGGER"
                confidence = 85
                reason = "M15 buy trigger: Price > EMA20, MACD bullish cross, RSI > 50"
            elif close > ema20 and rsi > 45:
                trigger = "BUY_WATCH"
                confidence = 65
                reason = "M15 potential buy - waiting for MACD confirmation"
        
        elif m30_setup == "SELL_SETUP":
            if close < ema20 and macd < macd_signal and rsi < 50:
                trigger = "SELL_TRIGGER"
                confidence = 85
                reason = "M15 sell trigger: Price < EMA20, MACD bearish cross, RSI < 50"
            elif close < ema20 and rsi < 55:
                trigger = "SELL_WATCH"
                confidence = 65
                reason = "M15 potential sell - waiting for MACD confirmation"
        
        else:
            trigger = "WAIT"
            confidence = 30
            reason = "M15 no trigger - M30 setup not ready"
        
        return {
            "trigger": trigger,
            "confidence": confidence,
            "reason": reason,
            "rsi": rsi,
            "macd_status": "bullish" if macd > macd_signal else "bearish",
            "price_vs_ema20": "above" if close > ema20 else "below",
            "verdict": f"M15 Trigger: {trigger} ({confidence}% confidence)",
            "choch_detected": choch_detected,
            "choch_bull": choch_bull,
            "choch_bear": choch_bear,
            "bos_detected": bos_detected,
            "bos_bull": bos_bull,
            "bos_bear": bos_bear
        }
    
    def _analyze_m5_execution(self, m5_data: Dict, m15_analysis: Dict, symbol: str) -> Dict:
        """
        M5 = Execution Frame
        Provides precise entry timing and stop placement
        """
        if not m5_data:
            return {"execution": "NONE", "confidence": 0, "reason": "No M5 data"}
        
        # Initialize CHOCH/BOS defaults
        choch_detected = False
        choch_bull = False
        choch_bear = False
        bos_detected = False
        bos_bull = False
        bos_bear = False
        
        try:
            if m5_data:
                opens = m5_data.get("opens", []) or []
                highs = m5_data.get("highs", []) or []
                lows = m5_data.get("lows", []) or []
                closes = m5_data.get("closes", []) or []
                
                if not isinstance(opens, list):
                    opens = []
                if not isinstance(highs, list):
                    highs = []
                if not isinstance(lows, list):
                    lows = []
                if not isinstance(closes, list):
                    closes = []
                
                if len(closes) >= 10:
                    times = m5_data.get("times", [])
                    if times and len(times) == len(closes):
                        try:
                            # Handle different time formats: Unix timestamps (int/float) or ISO strings
                            first_time = times[0] if times else None
                            if first_time is not None:
                                if isinstance(first_time, (int, float)):
                                    # Unix timestamp - check if seconds or milliseconds
                                    if first_time > 1e10:  # Likely milliseconds
                                        times_series = pd.to_datetime(times, unit='ms', errors='coerce')
                                    else:  # Likely seconds
                                        times_series = pd.to_datetime(times, unit='s', errors='coerce')
                                else:
                                    # String or datetime - use errors='coerce' to suppress warnings and handle parsing errors
                                    times_series = pd.to_datetime(times, errors='coerce')
                            else:
                                times_series = pd.to_datetime(times, errors='coerce')
                            times = (times_series.astype('int64') // 10**9).tolist()
                        except Exception:
                            times = list(range(len(closes)))
                    else:
                        times = list(range(len(closes)))
                    
                    bars_df = pd.DataFrame({
                        "open": opens,
                        "high": highs,
                        "low": lows,
                        "close": closes,
                        "time": times
                    })
                    
                    raw_swings = _symmetric_swings(bars_df, left=3, right=3, lookback=20)
                    
                    if raw_swings:
                        labeled_swings = label_swings(raw_swings)
                        
                        if labeled_swings:
                            swings_dict = [{"price": s.price, "kind": s.kind} for s in labeled_swings]
                            
                            current_close = float(closes[-1]) if closes else float(m5_data.get("current_close", 0))
                            
                            atr = float(m5_data.get("atr14", 0)) or float(m5_data.get("atr", 0))
                            if atr <= 0:
                                if len(closes) < 2:
                                    atr = 1.0
                                elif len(highs) >= 14 and len(lows) >= 14 and len(closes) >= 15:
                                    true_ranges = []
                                    for i in range(1, min(15, len(closes))):
                                        tr = max(
                                            highs[i] - lows[i],
                                            abs(highs[i] - closes[i-1]),
                                            abs(lows[i] - closes[i-1])
                                        )
                                        true_ranges.append(tr)
                                    atr = sum(true_ranges) / len(true_ranges) if true_ranges else 1.0
                                elif len(highs) >= 14 and len(lows) >= 14:
                                    recent_highs = highs[-14:]
                                    recent_lows = lows[-14:]
                                    if recent_highs and recent_lows:
                                        atr = (max(recent_highs) - min(recent_lows)) / 14
                                    else:
                                        atr = 1.0
                                else:
                                    atr = 1.0
                            
                            choch_bos_result = detect_bos_choch(swings_dict, current_close, atr)
                            
                            if choch_bos_result:
                                choch_bull = choch_bos_result.get("choch_bull", False)
                                choch_bear = choch_bos_result.get("choch_bear", False)
                                bos_bull = choch_bos_result.get("bos_bull", False)
                                bos_bear = choch_bos_result.get("bos_bear", False)
                                choch_detected = choch_bull or choch_bear
                                bos_detected = bos_bull or bos_bear
                                
                                if choch_detected or bos_detected:
                                    logger.debug(f"CHOCH/BOS detected for {symbol} M5: choch={choch_detected}, bos={bos_detected}")
        except Exception as e:
            logger.debug(f"CHOCH/BOS detection failed for {symbol} M5: {e}")
        
        atr = float(m5_data.get("atr14", 0))
        ema20 = float(m5_data.get("ema20", 0))
        
        close_data = m5_data.get("close", 0)
        if isinstance(close_data, list):
            close = float(close_data[-1]) if close_data else 0.0
        else:
            close = float(close_data) if close_data else 0.0
        close = float(m5_data.get("current_close", close))
        
        m15_trigger = m15_analysis.get("trigger", "NONE")
        
        # Determine M5 execution
        execution = "NONE"
        confidence = 50
        reason = ""
        entry_suggestion = None
        stop_suggestion = None
        
        if m15_trigger == "BUY_TRIGGER":
            execution = "BUY_NOW"
            confidence = 85
            entry_suggestion = close
            stop_suggestion = close - (atr * 1.5)
            reason = f"M5 ready for buy execution - Entry: {close:.2f}, SL: {stop_suggestion:.2f}"
        
        elif m15_trigger == "SELL_TRIGGER":
            execution = "SELL_NOW"
            confidence = 85
            entry_suggestion = close
            stop_suggestion = close + (atr * 1.5)
            reason = f"M5 ready for sell execution - Entry: {close:.2f}, SL: {stop_suggestion:.2f}"
        
        elif m15_trigger in ["BUY_WATCH", "SELL_WATCH"]:
            execution = "WAIT_FOR_M15"
            confidence = 60
            reason = "M5 ready but waiting for M15 confirmation"
        
        else:
            execution = "NO_TRADE"
            confidence = 30
            reason = "M5 no execution - higher timeframes not aligned"
        
        return {
            "execution": execution,
            "confidence": confidence,
            "reason": reason,
            "entry_price": entry_suggestion,
            "stop_loss": stop_suggestion,
            "atr": atr,
            "verdict": f"M5 Execution: {execution} ({confidence}% confidence)",
            "choch_detected": choch_detected,
            "choch_bull": choch_bull,
            "choch_bear": choch_bear,
            "bos_detected": bos_detected,
            "bos_bull": bos_bull,
            "bos_bear": bos_bear
        }
    
    def _determine_primary_trend(self, h4_analysis: Dict, h1_analysis: Dict) -> Dict:
        """
        Determine primary trend using hierarchical approach (H4 + H1 only)
        Lower timeframes cannot override this
        """
        h4_bias = h4_analysis.get("bias", "NEUTRAL")
        h4_conf = h4_analysis.get("confidence", 0)
        h1_status = h1_analysis.get("status", "NEUTRAL")
        h1_conf = h1_analysis.get("confidence", 0)
        
        # Step 1: Check H4 + H1 alignment
        if h4_bias == "BULLISH" and h1_status in ["CONTINUATION", "PULLBACK"]:
            primary_trend = "BULLISH"
            trend_strength = "STRONG" if (h4_conf >= 70 and h1_conf >= 70) else "MODERATE"
            confidence = (h4_conf + h1_conf) / 2
        elif h4_bias == "BEARISH" and h1_status in ["CONTINUATION", "PULLBACK"]:
            primary_trend = "BEARISH"
            trend_strength = "STRONG" if (h4_conf >= 70 and h1_conf >= 70) else "MODERATE"
            confidence = (h4_conf + h1_conf) / 2
        elif h4_bias == "NEUTRAL" or h1_status == "NEUTRAL":
            primary_trend = "NEUTRAL"
            trend_strength = "WEAK"
            confidence = (h4_conf + h1_conf) / 2
        elif h1_status == "DIVERGENCE":
            # H1 diverges from H4 - use H1's own bias from price/EMA
            price_vs_ema = h1_analysis.get("price_vs_ema20", "neutral")
            if price_vs_ema == "above" and h4_bias == "BULLISH":
                primary_trend = "BULLISH"
                trend_strength = "WEAK"
                confidence = (h4_conf + h1_conf) / 2
            elif price_vs_ema == "below" and h4_bias == "BEARISH":
                primary_trend = "BEARISH"
                trend_strength = "WEAK"
                confidence = (h4_conf + h1_conf) / 2
            else:
                primary_trend = "NEUTRAL"
                trend_strength = "WEAK"
                confidence = 40
        else:
            primary_trend = "NEUTRAL"
            trend_strength = "WEAK"
            confidence = 40
        
        return {
            "primary_trend": primary_trend,
            "trend_strength": trend_strength,
            "confidence": confidence,
            "h4_bias": h4_bias,
            "h1_status": h1_status,
            "locked": True  # Cannot be overridden by lower timeframes
        }
    
    def _detect_counter_trend_opportunities(self, primary_trend: Dict, m30, m15, m5) -> Dict:
        """
        Detect counter-trend opportunities with enhanced risk logic
        """
        primary_trend_direction = primary_trend.get("primary_trend", "NEUTRAL")
        
        # Determine lower timeframe bias from M15 trigger and M5 execution
        m15_trigger = m15.get("trigger", "NONE")
        m5_execution = m5.get("execution", "NONE")
        
        # Map triggers/executions to direction
        lower_tf_direction = None
        if m15_trigger in ["BUY_TRIGGER", "BUY_WATCH"] or m5_execution == "BUY_NOW":
            lower_tf_direction = "BULLISH"
        elif m15_trigger in ["SELL_TRIGGER", "SELL_WATCH"] or m5_execution == "SELL_NOW":
            lower_tf_direction = "BEARISH"
        
        # If no lower TF signal, return None
        if not lower_tf_direction or primary_trend_direction == "NEUTRAL":
            return None
        
        # Check if counter-trend
        is_counter_trend = (
            (primary_trend_direction == "BEARISH" and lower_tf_direction == "BULLISH") or
            (primary_trend_direction == "BULLISH" and lower_tf_direction == "BEARISH")
        )
        
        if is_counter_trend:
            trade_type = "COUNTER_TREND"
            direction = "BUY" if lower_tf_direction == "BULLISH" else "SELL"
            confidence = min(m15.get("confidence", 0), 60)  # Cap at 60%
            reason = f"M15 {m15_trigger} + M5 {m5_execution} (counter-trend in {primary_trend_direction.lower()} trend)"
        else:
            trade_type = "TREND_CONTINUATION"
            direction = "BUY" if lower_tf_direction == "BULLISH" else "SELL"
            confidence = m15.get("confidence", 0)
            reason = f"M15 {m15_trigger} + M5 {m5_execution} (trend continuation)"
        
        # Enhanced risk adjustments (from section 1.5)
        trend_strength = primary_trend.get("trend_strength", "MODERATE")
        if trade_type == "COUNTER_TREND":
            if trend_strength == "STRONG":
                risk_level = "HIGH"
                sl_multiplier = 1.25
                tp_multiplier = 0.50
                max_risk_rr = 0.5
            elif trend_strength == "MODERATE":
                risk_level = "MEDIUM"
                sl_multiplier = 1.15
                tp_multiplier = 0.75
                max_risk_rr = 0.75
            else:  # WEAK
                risk_level = "LOW"
                sl_multiplier = 1.0
                tp_multiplier = 1.0
                max_risk_rr = 1.0
        else:  # TREND_CONTINUATION
            risk_level = "LOW"
            sl_multiplier = 1.0
            tp_multiplier = 1.0
            max_risk_rr = 1.0
        
        return {
            "type": f"{trade_type}_{direction}",
            "direction": direction,
            "confidence": confidence,
            "risk_level": risk_level,
            "risk_adjustments": {
                "sl_multiplier": sl_multiplier,
                "tp_multiplier": tp_multiplier,
                "max_risk_rr": max_risk_rr
            },
            "reason": reason
        }
    
    def _get_volatility_based_weights(self) -> Dict:
        """
        Get dynamic timeframe weights based on volatility regime
        During high volatility, anchor to macro (H4/H1) and reduce lower TF noise
        """
        try:
            # Get volatility state from advanced features
            volatility_state_dict = self._analyze_volatility_state()
            volatility_state = volatility_state_dict.get("state", "unknown")
        except Exception as e:
            logger.debug(f"Could not analyze volatility state: {e}")
            volatility_state = "unknown"
        
        # Map volatility state to regime
        if volatility_state in ["expansion_strong_trend", "expansion_weak_trend"]:
            regime = "high"
        elif volatility_state in ["squeeze_no_trend", "squeeze_with_trend"]:
            regime = "low"
        else:
            regime = "medium"  # Default for unknown/None/other states
        
        return VOLATILITY_WEIGHTS.get(regime, VOLATILITY_WEIGHTS["medium"])
    
    def _update_trend_memory(self, timeframe: str, bias: str, confidence: int) -> Dict:
        """
        Maintain rolling 3-bar memory per timeframe to prevent rapid bias flipping
        Only shift bias if 3 consecutive bars confirm the change
        Thread-safe implementation
        """
        # Initialize if not exists (backward compatibility)
        if not hasattr(self, 'trend_memory'):
            if not hasattr(self, 'trend_memory_lock'):
                self.trend_memory_lock = threading.Lock()
            with self.trend_memory_lock:
                if not hasattr(self, 'trend_memory'):
                    self.trend_memory = {
                        "H4": [], "H1": [], "M30": [], "M15": [], "M5": []
                    }
        
        if timeframe not in self.trend_memory:
            return {"bias": bias, "confidence": confidence, "stability": "UNSTABLE"}
        
        # Thread-safe update
        with self.trend_memory_lock:
            # Add current bias to memory (keep last 3)
            self.trend_memory[timeframe].append({
                "bias": bias,
                "confidence": confidence,
                "timestamp": datetime.utcnow()
            })
            
            # Keep only last 3 bars
            if len(self.trend_memory[timeframe]) > 3:
                self.trend_memory[timeframe] = self.trend_memory[timeframe][-3:]
            
            # Check if 3 consecutive bars agree
            if len(self.trend_memory[timeframe]) == 3:
                biases = [bar["bias"] for bar in self.trend_memory[timeframe]]
                if all(b == biases[0] for b in biases):
                    # 3 bars agree - stable bias
                    avg_confidence = sum(bar["confidence"] for bar in self.trend_memory[timeframe]) / 3
                    return {
                        "bias": biases[0],
                        "confidence": avg_confidence,
                        "stability": "STABLE",
                        "confirmed_bars": 3
                    }
                else:
                    # Mixed signals - use most recent but mark as unstable
                    return {
                        "bias": biases[-1],
                        "confidence": self.trend_memory[timeframe][-1]["confidence"],
                        "stability": "UNSTABLE",
                        "confirmed_bars": 1
                    }
            else:
                # Not enough bars yet - use current
                return {
                    "bias": bias,
                    "confidence": confidence,
                    "stability": "INSUFFICIENT_DATA",
                    "confirmed_bars": len(self.trend_memory[timeframe])
                }
    
    def _map_h1_status_to_bias(self, h1_analysis: Dict, h4_bias: str) -> str:
        """
        Map H1 status (CONTINUATION/PULLBACK/DIVERGENCE) to bias (BULLISH/BEARISH/NEUTRAL)
        for trend memory buffer
        """
        h1_status = h1_analysis.get("status", "NEUTRAL")
        
        if h1_status == "CONTINUATION":
            # H1 continues H4 trend
            return h4_bias
        elif h1_status == "PULLBACK":
            # H1 pulls back but still in H4 trend direction
            return h4_bias
        elif h1_status == "DIVERGENCE":
            # H1 diverges from H4 - use H1's own bias from price/EMA
            price_vs_ema = h1_analysis.get("price_vs_ema20", "neutral")
            if price_vs_ema == "above":
                return "BULLISH"
            elif price_vs_ema == "below":
                return "BEARISH"
            else:
                return "NEUTRAL"
        else:
            return "NEUTRAL"
    
    def _calculate_alignment(self, h4, h1, m30, m15, m5) -> int:
        """
        Calculate overall timeframe alignment score (0-100)
        Enhanced with dynamic volatility weighting and V8 confidence adjustments
        """
        # Get dynamic weights based on volatility regime
        weights = self._get_volatility_based_weights()
        
        # Base alignment score using dynamic weights
        scores = [
            h4.get("confidence", 0) * weights.get("H4", 0.40),
            h1.get("confidence", 0) * weights.get("H1", 0.25),
            m30.get("confidence", 0) * weights.get("M30", 0.15),
            m15.get("confidence", 0) * weights.get("M15", 0.12),
            m5.get("confidence", 0) * weights.get("M5", 0.08)
        ]
        base_score = sum(scores)
        
        # Apply Advanced confidence adjustments if available
        if self.advanced_features:
            insights = self._generate_advanced_insights()
            
            # Aggregate Advanced confidence adjustments
            advanced_adjustment = 0
            advanced_adjustment += insights.get("rmag_analysis", {}).get("confidence_adjustment", 0)
            advanced_adjustment += insights.get("ema_slope_quality", {}).get("confidence_adjustment", 0)
            advanced_adjustment += insights.get("volatility_state", {}).get("confidence_adjustment", 0)
            advanced_adjustment += insights.get("momentum_quality", {}).get("confidence_adjustment", 0)
            advanced_adjustment += insights.get("mtf_alignment", {}).get("confidence_adjustment", 0)
            
            # Apply Advanced adjustment (capped at ±20 points)
            advanced_adjustment = max(-20, min(20, advanced_adjustment))
            
            logger.info(f"Advanced confidence adjustment: {advanced_adjustment:+d} points")
            
            final_score = base_score + advanced_adjustment
            return int(max(0, min(100, final_score)))  # Clamp to 0-100
        
        return int(base_score)
    
    def _generate_recommendation(self, h4, h1, m30, m15, m5, alignment_score) -> Dict:
        """Generate final trade recommendation with all enhancements"""
        try:
            # STEP 1: Apply trend memory buffer to H4 and H1
            try:
                h4_bias = h4.get("bias", "NEUTRAL")
                h4_conf = h4.get("confidence", 0)
                h4_stabilized = self._update_trend_memory("H4", h4_bias, h4_conf)
            except Exception as e:
                logger.debug(f"Trend memory update failed for H4: {e}")
                h4_bias = h4.get("bias", "NEUTRAL")
                h4_conf = h4.get("confidence", 0)
                h4_stabilized = {"bias": h4_bias, "confidence": h4_conf, "stability": "UNKNOWN"}
            
            try:
                h1_bias = self._map_h1_status_to_bias(h1, h4_bias)
                h1_conf = h1.get("confidence", 0)
                h1_stabilized = self._update_trend_memory("H1", h1_bias, h1_conf)
            except Exception as e:
                logger.debug(f"Trend memory update failed for H1: {e}")
                h1_bias = h1.get("status", "NEUTRAL")
                h1_conf = h1.get("confidence", 0)
                h1_stabilized = {"bias": h1_bias, "confidence": h1_conf, "stability": "UNKNOWN"}
            
            # Create stabilized analysis dicts
            h4_stabilized_analysis = h4.copy()
            h4_stabilized_analysis["bias"] = h4_stabilized["bias"]
            h4_stabilized_analysis["confidence"] = h4_stabilized["confidence"]
            
            h1_stabilized_analysis = h1.copy()  # Keep original status field
            h1_stabilized_analysis["bias"] = h1_stabilized["bias"]  # Add bias field, preserve original status
            h1_stabilized_analysis["confidence"] = h1_stabilized["confidence"]
            
            # STEP 2: Determine primary trend using stabilized H4/H1
            try:
                primary_trend = self._determine_primary_trend(h4_stabilized_analysis, h1_stabilized_analysis)
                primary_trend["stability"] = h4_stabilized.get("stability", "UNKNOWN")
            except Exception as e:
                logger.debug(f"Primary trend determination failed: {e}")
                primary_trend = {
                    "primary_trend": "NEUTRAL",
                    "trend_strength": "WEAK",
                    "confidence": 0,
                    "stability": "UNKNOWN"
                }
            
            # STEP 3: Get dynamic volatility weights
            try:
                volatility_weights = self._get_volatility_based_weights()
                volatility_state_dict = self._analyze_volatility_state()
                volatility_state = volatility_state_dict.get("state", "unknown")
                
                # Map to regime
                if volatility_state in ["expansion_strong_trend", "expansion_weak_trend"]:
                    volatility_regime = "high"
                elif volatility_state in ["squeeze_no_trend", "squeeze_with_trend"]:
                    volatility_regime = "low"
                else:
                    volatility_regime = "medium"
            except Exception as e:
                logger.debug(f"Volatility analysis failed: {e}")
                volatility_regime = "medium"
                volatility_weights = VOLATILITY_WEIGHTS.get("medium", VOLATILITY_WEIGHTS["medium"])
            
            # STEP 4: Alignment score already calculated with dynamic weights in _calculate_alignment()
            # (alignment_score parameter passed to this method)
            
            # STEP 5: Detect counter-trend opportunities
            try:
                trade_opportunities = self._detect_counter_trend_opportunities(primary_trend, m30, m15, m5)
                if trade_opportunities is None:
                    trade_opportunities = {
                        "type": "NONE",
                        "direction": "NONE",
                        "confidence": 0,
                        "risk_level": "UNKNOWN",
                        "risk_adjustments": {},
                        "reason": "No trade opportunity detected"
                    }
            except Exception as e:
                logger.debug(f"Counter-trend detection failed: {e}")
                trade_opportunities = {
                    "type": "NONE",
                    "direction": "NONE",
                    "confidence": 0,
                    "risk_level": "UNKNOWN",
                    "risk_adjustments": {},
                    "reason": f"Error detecting opportunities: {e}"
                }
            
            # STEP 6: Determine action from trade opportunities or alignment
            if trade_opportunities.get("type") != "NONE":
                action = trade_opportunities.get("direction", "WAIT")
                confidence = trade_opportunities.get("confidence", alignment_score)
                reason = trade_opportunities.get("reason", "")
            else:
                # Fallback to alignment-based recommendation (backward compatible)
                m15_trigger = m15.get("trigger", "NONE")
                m5_execution = m5.get("execution", "NONE")
                if alignment_score >= 75 and m5_execution in ["BUY_NOW", "SELL_NOW"]:
                    action = m5_execution.replace("_NOW", "")
                    confidence = alignment_score
                    reason = f"Strong multi-timeframe alignment ({alignment_score}/100)"
                elif alignment_score >= 60 and m15_trigger in ["BUY_TRIGGER", "SELL_TRIGGER"]:
                    action = m15_trigger.replace("_TRIGGER", "")
                    confidence = alignment_score
                    reason = f"Good multi-timeframe alignment ({alignment_score}/100)"
                else:
                    action = "WAIT"
                    confidence = alignment_score
                    reason = f"Weak alignment ({alignment_score}/100) - wait for better setup"
            
            # Add Advanced context to reason if available
            if self.advanced_features:
                advanced_summary = self._generate_advanced_summary()
                if advanced_summary and advanced_summary != "Advanced Analysis: Normal market conditions":
                    reason += f" | {advanced_summary}"
            
            # Build backward-compatible structure (for existing API consumers)
            backward_compatible = {
                "action": action,
                "confidence": confidence,
                "reason": reason,
                "h4_bias": h4_bias,
                "entry_price": m5.get("entry_price"),
                "stop_loss": m5.get("stop_loss"),
                "summary": (
                    f"H4: {h4_bias} | "
                    f"H1: {h1.get('status', 'UNKNOWN')} | "
                    f"M30: {m30.get('setup', 'NONE')} | "
                    f"M15: {m15.get('trigger', 'NONE')} | "
                    f"M5: {m5.get('execution', 'NONE')}"
                )
            }
            
            # Build new hierarchical structure
            hierarchical_result = {
                "market_bias": {
                    "trend": primary_trend.get("primary_trend", "NEUTRAL"),
                    "strength": primary_trend.get("trend_strength", "WEAK"),
                    "confidence": primary_trend.get("confidence", 0),
                    "stability": primary_trend.get("stability", "UNKNOWN"),
                    "reason": f"H4 {h4_bias} ({h4_conf}%) + H1 {h1.get('status', 'UNKNOWN')} ({h1_conf}%)"
                },
                "trade_opportunities": trade_opportunities,
                "volatility_regime": volatility_regime,
                "volatility_weights": volatility_weights
            }
            
            # Merge both structures (backward compatible + new hierarchical fields)
            result = backward_compatible.copy()
            result.update(hierarchical_result)
            result["recommendation"] = backward_compatible  # Nested for new consumers
            
            return result
        
        except Exception as e:
            logger.error(f"Error in _generate_recommendation: {e}", exc_info=True)
            # Return minimal backward-compatible structure on error
            h4_bias = h4.get("bias", "UNKNOWN") if h4 else "UNKNOWN"
            return {
                "action": "WAIT",
                "confidence": 0,
                "reason": f"Error generating recommendation: {e}",
                "h4_bias": h4_bias,
                "summary": "Error in recommendation generation",
                "market_bias": {"trend": "UNKNOWN", "strength": "UNKNOWN", "confidence": 0},
                "trade_opportunities": {"type": "NONE"},
                "volatility_regime": "medium",
                "volatility_weights": {}
            }
    
    def _empty_result(self, symbol: str) -> Dict:
        """Return empty result when data unavailable"""
        return {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "timeframes": {},
            "alignment_score": 0,
            "recommendation": {
                "action": "WAIT",
                "confidence": 0,
                "reason": "No data available",
                "summary": "Unable to analyze - no market data"
            }
        }
    
    def _fetch_advanced_features(self, symbol: str) -> Optional[Dict]:
        """Fetch Advanced technical features"""
        try:
            from infra.feature_builder_advanced import build_features_advanced
            
            if not self.mt5_service or not self.indicator_bridge:
                logger.debug("Advanced features unavailable: MT5 service or indicator bridge not initialized")
                return None
            
            v8_data = build_features_advanced(
                symbol=symbol,
                mt5svc=self.mt5_service,
                bridge=self.indicator_bridge,
                timeframes=["M5", "M15", "H1"]
            )
            
            if v8_data and "features" in v8_data:
                logger.info(f"✅ Advanced features loaded for multi-timeframe analysis: {symbol}")
                return v8_data.get("features", {})
            
            return None
            
        except Exception as e:
            logger.debug(f"Advanced features not available: {e}")
            return None
    
    def _generate_advanced_insights(self) -> Dict:
        """Generate structured Advanced insights from features"""
        if not self.advanced_features:
            return {}
        
        insights = {
            "rmag_analysis": self._analyze_rmag(),
            "ema_slope_quality": self._analyze_ema_slope(),
            "volatility_state": self._analyze_volatility_state(),
            "momentum_quality": self._analyze_momentum_quality(),
            "mtf_alignment": self._analyze_mtf_alignment(),
            "market_structure": self._analyze_market_structure_advanced()
        }
        
        return insights
    
    def _analyze_rmag(self) -> Dict:
        """Analyze RMAG (Relative Moving Average Gap)"""
        if not self.advanced_features:
            return {}
        
        m5_rmag = self.advanced_features.get("M5", {}).get("rmag", {})
        ema200_atr = m5_rmag.get("ema200_atr", 0)
        vwap_atr = m5_rmag.get("vwap_atr", 0)
        
        if abs(ema200_atr) > 2.0:
            status = "STRETCHED"
            interpretation = f"Price is {abs(ema200_atr):.1f}σ from EMA200 - expect mean reversion"
            confidence_adjustment = -15
        elif abs(ema200_atr) > 1.5:
            status = "EXTENDED"
            interpretation = f"Price moderately stretched ({abs(ema200_atr):.1f}σ) - caution on new entries"
            confidence_adjustment = -5
        else:
            status = "NORMAL"
            interpretation = f"Price within normal range ({abs(ema200_atr):.1f}σ) - safe to trade"
            confidence_adjustment = 0
        
        return {
            "status": status,
            "ema200_stretch": ema200_atr,
            "vwap_stretch": vwap_atr,
            "interpretation": interpretation,
            "confidence_adjustment": confidence_adjustment
        }
    
    def _analyze_ema_slope(self) -> Dict:
        """Analyze EMA Slope Strength"""
        if not self.advanced_features:
            return {}
        
        m15_slope = self.advanced_features.get("M15", {}).get("ema_slope", {})
        ema50 = m15_slope.get("ema50", 0)
        ema200 = m15_slope.get("ema200", 0)
        
        if ema50 > 0.15 and ema200 > 0.05:
            quality = "QUALITY_UPTREND"
            interpretation = "Strong uptrend with quality EMA slopes"
            confidence_adjustment = +10
        elif ema50 < -0.15 and ema200 < -0.05:
            quality = "QUALITY_DOWNTREND"
            interpretation = "Strong downtrend with quality EMA slopes"
            confidence_adjustment = +10
        elif abs(ema50) < 0.05 and abs(ema200) < 0.03:
            quality = "FLAT"
            interpretation = "Flat EMAs - avoid trend trades"
            confidence_adjustment = -10
        else:
            quality = "MODERATE"
            interpretation = "Moderate trend - proceed with caution"
            confidence_adjustment = 0
        
        return {
            "quality": quality,
            "ema50_slope": ema50,
            "ema200_slope": ema200,
            "interpretation": interpretation,
            "confidence_adjustment": confidence_adjustment
        }
    
    def _analyze_volatility_state(self) -> Dict:
        """Analyze Bollinger-ADX Fusion (Volatility State)"""
        if not self.advanced_features:
            return {}
        
        m15_vol = self.advanced_features.get("M15", {}).get("vol_trend", {})
        state = m15_vol.get("state", "unknown")
        bb_width = m15_vol.get("bb_width", 0)
        adx = m15_vol.get("adx", 0)
        
        interpretations = {
            "squeeze_no_trend": {
                "action": "WAIT",
                "interpretation": "Low volatility squeeze - anticipate breakout, wait for momentum",
                "confidence_adjustment": -10
            },
            "squeeze_with_trend": {
                "action": "CAUTION",
                "interpretation": "Choppy consolidation within trend - proceed with caution",
                "confidence_adjustment": -5
            },
            "expansion_strong_trend": {
                "action": "RIDE",
                "interpretation": "High volatility with strong trend - momentum continuation likely",
                "confidence_adjustment": +10
            },
            "expansion_weak_trend": {
                "action": "AVOID",
                "interpretation": "Volatile but directionless - range trading only",
                "confidence_adjustment": -10
            }
        }
        
        state_info = interpretations.get(state, {
            "action": "NEUTRAL",
            "interpretation": "Unknown volatility state",
            "confidence_adjustment": 0
        })
        
        return {
            "state": state,
            "bb_width": bb_width,
            "adx": adx,
            "action": state_info["action"],
            "interpretation": state_info["interpretation"],
            "confidence_adjustment": state_info["confidence_adjustment"]
        }
    
    def _analyze_momentum_quality(self) -> Dict:
        """Analyze RSI-ADX Pressure Ratio (Momentum Quality)"""
        if not self.advanced_features:
            return {}
        
        m15_pressure = self.advanced_features.get("M15", {}).get("pressure", {})
        ratio = m15_pressure.get("ratio", 0)
        rsi = m15_pressure.get("rsi", 50)
        adx = m15_pressure.get("adx", 0)
        
        if rsi > 60 and adx < 20 and ratio > 3.0:
            quality = "FAKE_MOMENTUM"
            interpretation = f"High RSI ({rsi:.0f}) but weak ADX ({adx:.0f}) - fake momentum, fade risk"
            confidence_adjustment = -10
        elif rsi > 60 and adx > 30:
            quality = "QUALITY_MOMENTUM"
            interpretation = f"High RSI ({rsi:.0f}) with strong ADX ({adx:.0f}) - quality trend momentum"
            confidence_adjustment = +10
        elif rsi < 40 and adx < 20:
            quality = "FAKE_WEAKNESS"
            interpretation = f"Low RSI ({rsi:.0f}) but weak ADX ({adx:.0f}) - fake weakness, bounce risk"
            confidence_adjustment = -10
        else:
            quality = "NORMAL"
            interpretation = "Normal momentum conditions"
            confidence_adjustment = 0
        
        return {
            "quality": quality,
            "ratio": ratio,
            "rsi": rsi,
            "adx": adx,
            "interpretation": interpretation,
            "confidence_adjustment": confidence_adjustment
        }
    
    def _analyze_mtf_alignment(self) -> Dict:
        """Analyze Multi-Timeframe Alignment Score"""
        if not self.advanced_features:
            return {}
        
        mtf_score = self.advanced_features.get("mtf_score", {})
        total = mtf_score.get("total", 0)
        m5 = mtf_score.get("m5", 0)
        m15 = mtf_score.get("m15", 0)
        h1 = mtf_score.get("h1", 0)
        max_score = mtf_score.get("max", 3)
        
        if total >= 2:
            status = "STRONG_ALIGNMENT"
            interpretation = f"Strong confluence ({total}/{max_score} timeframes aligned)"
            confidence_adjustment = +10
        elif total == 1:
            status = "WEAK_ALIGNMENT"
            interpretation = f"Weak confluence ({total}/{max_score} timeframe aligned) - mixed signals"
            confidence_adjustment = -5
        else:
            status = "NO_ALIGNMENT"
            interpretation = "No timeframe agreement - avoid trade"
            confidence_adjustment = -15
        
        return {
            "status": status,
            "total": total,
            "max": max_score,
            "m5_aligned": bool(m5),
            "m15_aligned": bool(m15),
            "h1_aligned": bool(h1),
            "interpretation": interpretation,
            "confidence_adjustment": confidence_adjustment
        }
    
    def _analyze_market_structure_advanced(self) -> Dict:
        """Analyze market structure using Advanced features"""
        if not self.advanced_features:
            return {}
        
        m5_features = self.advanced_features.get("M5", {})
        
        # Liquidity analysis
        liquidity = m5_features.get("liquidity", {})
        pdl_dist = liquidity.get("pdl_dist_atr", 999)
        pdh_dist = liquidity.get("pdh_dist_atr", 999)
        equal_highs = liquidity.get("equal_highs", False)
        equal_lows = liquidity.get("equal_lows", False)
        
        # FVG analysis
        fvg = m5_features.get("fvg")
        fvg_nearby = False
        fvg_info = None
        if fvg and isinstance(fvg, dict):
            dist_to_fill = fvg.get("dist_to_fill_atr", 999)
            if dist_to_fill < 1.0:
                fvg_nearby = True
                fvg_info = {
                    "type": fvg.get("type", "unknown"),
                    "distance": dist_to_fill,
                    "interpretation": f"{fvg.get('type', 'unknown').title()} FVG nearby ({dist_to_fill:.1f} ATR) - likely fill target"
                }
        
        # VWAP deviation
        vwap = m5_features.get("vwap", {})
        vwap_zone = vwap.get("zone", "inside")
        vwap_dev = vwap.get("dev_atr", 0)
        
        return {
            "liquidity_risk": pdl_dist < 0.5 or pdh_dist < 0.5 or equal_highs or equal_lows,
            "pdl_distance": pdl_dist,
            "pdh_distance": pdh_dist,
            "equal_highs": equal_highs,
            "equal_lows": equal_lows,
            "fvg_nearby": fvg_nearby,
            "fvg_info": fvg_info,
            "vwap_zone": vwap_zone,
            "vwap_deviation": vwap_dev,
            "mean_reversion_risk": vwap_zone == "outer"
        }
    
    def _generate_advanced_summary(self) -> str:
        """Generate human-readable Advanced summary"""
        if not self.advanced_features:
            return "Advanced features unavailable"
        
        insights = self._generate_advanced_insights()
        
        summary_parts = []
        
        # RMAG
        rmag = insights.get("rmag_analysis", {})
        if rmag.get("status") == "STRETCHED":
            summary_parts.append(f"⚠️ Price stretched ({rmag.get('ema200_stretch', 0):.1f}σ)")
        
        # EMA Slope
        ema_slope = insights.get("ema_slope_quality", {})
        if ema_slope.get("quality") in ["QUALITY_UPTREND", "QUALITY_DOWNTREND"]:
            summary_parts.append(f"✅ {ema_slope.get('quality').replace('_', ' ').title()}")
        elif ema_slope.get("quality") == "FLAT":
            summary_parts.append("⚠️ Flat market")
        
        # Volatility State
        vol_state = insights.get("volatility_state", {})
        if vol_state.get("state") == "squeeze_no_trend":
            summary_parts.append("⏳ Squeeze - wait for breakout")
        elif vol_state.get("state") == "expansion_strong_trend":
            summary_parts.append("✅ Strong trend expansion")
        
        # Momentum Quality
        momentum = insights.get("momentum_quality", {})
        if momentum.get("quality") == "FAKE_MOMENTUM":
            summary_parts.append("⚠️ Fake momentum (high RSI + weak ADX)")
        elif momentum.get("quality") == "QUALITY_MOMENTUM":
            summary_parts.append("✅ Quality momentum")
        
        # MTF Alignment
        mtf = insights.get("mtf_alignment", {})
        total = mtf.get("total", 0)
        if total >= 2:
            summary_parts.append(f"✅ MTF Aligned ({total}/3)")
        elif total == 0:
            summary_parts.append("⚠️ No MTF alignment")
        
        # Market Structure
        structure = insights.get("market_structure", {})
        if structure.get("liquidity_risk"):
            summary_parts.append("⚠️ Near liquidity zone")
        if structure.get("fvg_nearby"):
            fvg_info = structure.get("fvg_info", {})
            summary_parts.append(f"🎯 {fvg_info.get('type', 'FVG').title()} FVG nearby")
        if structure.get("mean_reversion_risk"):
            summary_parts.append("⚠️ Far from VWAP (mean reversion risk)")
        
        if not summary_parts:
            return "Advanced Analysis: Normal market conditions"
        
        return "Advanced Analysis: " + " | ".join(summary_parts)
