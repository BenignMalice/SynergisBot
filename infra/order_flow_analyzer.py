"""
Order Flow Analyzer

Combines order book depth and aggregate trades to generate
institutional-grade order flow signals.
"""

import logging
from typing import Dict, Optional
from infra.binance_depth_stream import OrderBookAnalyzer
from infra.binance_aggtrades_stream import WhaleDetector

logger = logging.getLogger(__name__)


class OrderFlowAnalyzer:
    """
    Analyze order flow by combining:
    - Order book depth (liquidity)
    - Aggregate trades (large orders)
    - Market microstructure
    
    Generates signals for:
    - Stop hunt zones
    - Liquidity voids
    - Whale accumulation/distribution
    - Order book imbalance
    """
    
    def __init__(self):
        """Initialize order flow analyzer"""
        self.depth_analyzer = OrderBookAnalyzer(history_size=10)
        self.whale_detector = WhaleDetector(history_window=60)
        
        logger.info("📊 OrderFlowAnalyzer initialized")
    
    def update_depth(self, symbol: str, depth: Dict):
        """Update with new order book depth"""
        self.depth_analyzer.update(symbol, depth)
    
    def update_trade(self, symbol: str, trade: Dict):
        """Update with new aggregate trade"""
        self.whale_detector.update(symbol, trade)
        
        # Log whale orders
        whale_size = self.whale_detector.is_whale_order(trade)
        if whale_size:
            emoji = "🐋" if whale_size == "whale" else "🐟" if whale_size == "large" else "🦈"
            logger.info(
                f"{emoji} {whale_size.upper()} order detected: "
                f"{symbol} {trade['side']} ${trade['usd_value']:,.0f} @ {trade['price']:.2f}"
            )
    
    def get_order_flow_signal(self, symbol: str) -> Optional[Dict]:
        """
        Generate comprehensive order flow signal.
        
        Returns:
            {
                "symbol": str,
                "order_book": {...},  # Depth analysis
                "whale_activity": {...},  # Large orders
                "pressure": {...},  # Buy/sell pressure
                "signal": str,  # "BULLISH", "BEARISH", "NEUTRAL"
                "confidence": float,  # 0-100
                "warnings": [...]  # List of warnings
            }
        """
        signal = {
            "symbol": symbol,
            "order_book": None,
            "whale_activity": None,
            "pressure": None,
            "liquidity_voids": [],
            "signal": "NEUTRAL",
            "confidence": 0,
            "warnings": []
        }
        
        # 1. Order Book Analysis
        imbalance = self.depth_analyzer.calculate_imbalance(symbol, levels=5)
        voids = self.depth_analyzer.detect_liquidity_voids(symbol)
        liquidity = self.depth_analyzer.get_total_liquidity(symbol, levels=10)
        best_prices = self.depth_analyzer.get_best_bid_ask(symbol)
        
        if imbalance and liquidity:
            signal["order_book"] = {
                "imbalance": imbalance,
                "imbalance_pct": (imbalance - 1) * 100,
                "bid_liquidity": liquidity["bid_liquidity"],
                "ask_liquidity": liquidity["ask_liquidity"],
                "total_liquidity": liquidity["total"],
                "spread": best_prices["spread"] if best_prices else None,
                "spread_pct": best_prices["spread_pct"] if best_prices else None
            }
        
        signal["liquidity_voids"] = voids
        
        # 2. Whale Activity
        recent_whales = self.whale_detector.get_recent_whales(symbol, min_size="medium")
        if recent_whales:
            buy_whales = [w for w in recent_whales if w["side"] == "BUY"]
            sell_whales = [w for w in recent_whales if w["side"] == "SELL"]
            
            signal["whale_activity"] = {
                "total_whales": len(recent_whales),
                "buy_whales": len(buy_whales),
                "sell_whales": len(sell_whales),
                "largest_buy": max([w["usd_value"] for w in buy_whales], default=0),
                "largest_sell": max([w["usd_value"] for w in sell_whales], default=0),
                "net_whale_side": "BUY" if len(buy_whales) > len(sell_whales) else "SELL" if len(sell_whales) > len(buy_whales) else "NEUTRAL"
            }
        
        # 3. Buy/Sell Pressure
        pressure_30s = self.whale_detector.get_pressure(symbol, window=30)
        if pressure_30s:
            signal["pressure"] = {
                "buy_volume": pressure_30s["buy_volume"],
                "sell_volume": pressure_30s["sell_volume"],
                "pressure_ratio": pressure_30s["pressure"],
                "net_volume": pressure_30s["net_volume"],
                "dominant_side": pressure_30s["dominant_side"]
            }
        
        # 4. Volume Spike Detection
        volume_spike = self.whale_detector.get_volume_spike(symbol, current_window=10, baseline_window=60)
        if volume_spike and volume_spike > 2.0:
            signal["warnings"].append(f"Volume spike: {volume_spike:.1f}x normal")
        
        # 5. Generate Signal
        bullish_score = 0
        bearish_score = 0
        
        # Order book imbalance
        if imbalance:
            if imbalance > 1.3:
                bullish_score += 30
            elif imbalance < 0.7:
                bearish_score += 30
        
        # Whale activity
        if signal["whale_activity"]:
            if signal["whale_activity"]["buy_whales"] > signal["whale_activity"]["sell_whales"] * 1.5:
                bullish_score += 25
            elif signal["whale_activity"]["sell_whales"] > signal["whale_activity"]["buy_whales"] * 1.5:
                bearish_score += 25
        
        # Pressure
        if pressure_30s:
            if pressure_30s["pressure"] > 1.5:
                bullish_score += 25
            elif pressure_30s["pressure"] < 0.67:
                bearish_score += 25
        
        # Liquidity voids
        if voids:
            signal["warnings"].append(f"Liquidity voids detected: {len(voids)} zones")
            # Voids can indicate upcoming volatility
            if any(v["side"] == "ask" for v in voids):
                signal["warnings"].append("Void above price - potential for sharp move up")
            if any(v["side"] == "bid" for v in voids):
                signal["warnings"].append("Void below price - potential for sharp move down")
        
        # Determine signal
        if bullish_score > bearish_score and bullish_score >= 50:
            signal["signal"] = "BULLISH"
            signal["confidence"] = min(bullish_score, 100)
        elif bearish_score > bullish_score and bearish_score >= 50:
            signal["signal"] = "BEARISH"
            signal["confidence"] = min(bearish_score, 100)
        else:
            signal["signal"] = "NEUTRAL"
            signal["confidence"] = 0
        
        return signal
    
    def format_signal_summary(self, symbol: str) -> str:
        """
        Format order flow signal as human-readable text.
        
        Returns:
            Formatted string summary
        """
        signal = self.get_order_flow_signal(symbol)
        if not signal:
            return f"⚠️ No order flow data available for {symbol}"
        
        lines = []
        lines.append(f"📊 Order Flow Analysis - {symbol}")
        lines.append(f"Signal: {signal['signal']} ({signal['confidence']:.0f}% confidence)")
        lines.append("")
        
        # Order Book
        if signal["order_book"]:
            ob = signal["order_book"]
            imb_emoji = "🟢" if ob["imbalance"] > 1.2 else "🔴" if ob["imbalance"] < 0.8 else "⚪"
            lines.append(f"{imb_emoji} Order Book Imbalance: {ob['imbalance']:.2f} ({ob['imbalance_pct']:+.1f}%)")
            lines.append(f"   Bid Liquidity: ${ob['bid_liquidity']:,.0f}")
            lines.append(f"   Ask Liquidity: ${ob['ask_liquidity']:,.0f}")
            if ob["spread_pct"]:
                lines.append(f"   Spread: {ob['spread_pct']:.3f}%")
        
        # Whale Activity
        if signal["whale_activity"]:
            wa = signal["whale_activity"]
            whale_emoji = "🐋" if wa["total_whales"] > 5 else "🦈"
            lines.append(f"\n{whale_emoji} Whale Activity (60s window):")
            lines.append(f"   Total Whales: {wa['total_whales']}")
            lines.append(f"   Buy Whales: {wa['buy_whales']} (${wa['largest_buy']:,.0f} largest)")
            lines.append(f"   Sell Whales: {wa['sell_whales']} (${wa['largest_sell']:,.0f} largest)")
            lines.append(f"   Net Side: {wa['net_whale_side']}")
        
        # Pressure
        if signal["pressure"]:
            pr = signal["pressure"]
            pressure_emoji = "🟢" if pr["dominant_side"] == "BUY" else "🔴" if pr["dominant_side"] == "SELL" else "⚪"
            lines.append(f"\n{pressure_emoji} Order Flow Pressure (30s):")
            lines.append(f"   Ratio: {pr['pressure_ratio']:.2f} ({pr['dominant_side']})")
            lines.append(f"   Buy Volume: {pr['buy_volume']:.4f}")
            lines.append(f"   Sell Volume: {pr['sell_volume']:.4f}")
            lines.append(f"   Net: {pr['net_volume']:+.4f}")
        
        # Liquidity Voids
        if signal["liquidity_voids"]:
            lines.append(f"\n⚠️ Liquidity Voids: {len(signal['liquidity_voids'])} detected")
            for void in signal["liquidity_voids"][:3]:  # Show top 3
                lines.append(f"   {void['side'].upper()}: {void['price_from']:.2f} → {void['price_to']:.2f} (severity: {void['severity']:.1f}x)")
        
        # Warnings
        if signal["warnings"]:
            lines.append(f"\n⚠️ Warnings:")
            for warning in signal["warnings"]:
                lines.append(f"   • {warning}")
        
        return "\n".join(lines)
    
    def get_phase3_microstructure_metrics(self, symbol: str) -> Optional[Dict]:
        """
        Phase III: Get order flow microstructure metrics.
        
        Returns:
            {
                "imbalance": {
                    "imbalance_detected": bool,
                    "imbalance_ratio": float,
                    "imbalance_direction": "buy" | "sell" | None,
                    "bid_volume": float,
                    "ask_volume": float
                },
                "spoofing": {
                    "spoof_detected": bool,
                    "spoof_events": int,
                    "largest_spoof_size_usd": float,
                    "cancellation_rate": float
                },
                "rebuild_speed": {
                    "bid_rebuild_speed": float,
                    "ask_decay_speed": float,
                    "bid_depth_change": float,
                    "ask_depth_change": float,
                    "liquidity_rebuild_confirmed": bool
                }
            } or None
        """
        try:
            imbalance_data = self.depth_analyzer.detect_imbalance_with_direction(symbol, levels=5, threshold=1.5)
            spoof_data = self.depth_analyzer.detect_spoofing(symbol, min_order_size_usd=10000.0, max_lifetime_seconds=5.0)
            rebuild_data = self.depth_analyzer.calculate_rebuild_speed(symbol, window_seconds=20)
            
            return {
                "imbalance": imbalance_data,
                "spoofing": spoof_data,
                "rebuild_speed": rebuild_data
            }
        except Exception as e:
            logger.error(f"Error getting Phase III microstructure metrics for {symbol}: {e}", exc_info=True)
            return None

