"""
Classification Metrics Component (AIES Phase 1 MVP)

Collects and reports metrics on trade classification (SCALP vs INTRADAY).
Provides daily log summaries, Discord notifications, and aggregate statistics.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import deque, defaultdict
from dataclasses import dataclass, field
import logging
import time
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class ClassificationMetric:
    """Single trade classification metric"""
    timestamp: datetime
    ticket: Optional[int]
    symbol: str
    trade_type: str  # "SCALP" or "INTRADAY"
    confidence: float  # 0.0-1.0
    reasoning: str
    factor_used: str  # "keyword", "stop_atr_ratio", "session_strategy", "override", "default"
    latency_ms: float
    feature_enabled: bool = True


@dataclass
class AggregateMetrics:
    """Aggregate metrics for a window of trades"""
    window_size: int
    total_trades: int
    scalp_count: int = 0
    intraday_count: int = 0
    override_count: int = 0
    default_fallback_count: int = 0
    
    # Confidence distribution
    high_confidence_count: int = 0  # >= 0.7
    medium_confidence_count: int = 0  # 0.4-0.69
    low_confidence_count: int = 0  # < 0.4
    
    # Factor usage
    keyword_match_count: int = 0
    stop_atr_ratio_count: int = 0
    session_strategy_count: int = 0
    override_count_factor: int = 0
    default_fallback_count_factor: int = 0
    
    # Performance
    total_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    timeout_count: int = 0
    
    # Timestamps for filtering
    first_trade_time: Optional[datetime] = None
    last_trade_time: Optional[datetime] = None


class ClassificationMetrics:
    """
    Collects and aggregates trade classification metrics.
    
    Provides:
    - Per-trade metrics collection
    - Rolling window aggregate statistics
    - Formatted summary generation
    - Discord notification support
    """
    
    def __init__(self, window_size: int = 100, enabled: bool = True):
        """
        Initialize metrics collector.
        
        Args:
            window_size: Size of rolling window for aggregate metrics
            enabled: Whether metrics collection is enabled
        """
        self.window_size = window_size
        self.enabled = enabled
        self._lock = Lock()
        
        # Rolling window buffer (FIFO)
        self._metrics_buffer: deque[ClassificationMetric] = deque(maxlen=window_size)
        
        # Aggregate metrics cache
        self._aggregate_cache: Optional[AggregateMetrics] = None
        self._cache_valid = False
        
        logger.info(f"ClassificationMetrics initialized: window_size={window_size}, enabled={enabled}")
    
    def record_classification(
        self,
        ticket: Optional[int],
        symbol: str,
        trade_type: str,
        confidence: float,
        reasoning: str,
        factor_used: str,
        latency_ms: float,
        feature_enabled: bool = True
    ) -> None:
        """
        Record a single trade classification metric.
        
        Args:
            ticket: Position ticket number
            symbol: Trading symbol
            trade_type: "SCALP" or "INTRADAY"
            confidence: Confidence score (0.0-1.0)
            reasoning: Classification reasoning string
            factor_used: Which factor determined classification ("keyword", "stop_atr_ratio", "session_strategy", "override", "default")
            latency_ms: Classification latency in milliseconds
            feature_enabled: Whether classification feature was enabled
        """
        if not self.enabled:
            return
        
        try:
            metric = ClassificationMetric(
                timestamp=datetime.utcnow(),
                ticket=ticket,
                symbol=symbol,
                trade_type=trade_type.upper(),
                confidence=max(0.0, min(1.0, confidence)),  # Clamp to [0, 1]
                reasoning=reasoning,
                factor_used=factor_used.lower(),
                latency_ms=max(0.0, latency_ms),
                feature_enabled=feature_enabled
            )
            
            with self._lock:
                self._metrics_buffer.append(metric)
                self._cache_valid = False  # Invalidate cache
            
            logger.debug(
                f"📊 Classification metric recorded: {trade_type} "
                f"(confidence={confidence:.2f}, factor={factor_used}, latency={latency_ms:.1f}ms)"
            )
            
        except Exception as e:
            logger.warning(f"Failed to record classification metric: {e}")
    
    def get_aggregate_metrics(
        self,
        window_size: Optional[int] = None,
        since: Optional[datetime] = None
    ) -> AggregateMetrics:
        """
        Calculate aggregate metrics for the rolling window.
        
        Args:
            window_size: Override default window size (uses last N trades)
            since: Filter metrics since this timestamp (uses time-based window)
        
        Returns:
            AggregateMetrics object with aggregated statistics
        """
        with self._lock:
            # Use cached result if valid
            if self._cache_valid and self._aggregate_cache and not window_size and not since:
                return self._aggregate_cache
            
            # Determine which metrics to include
            if since:
                # Time-based window: include all trades since timestamp
                metrics_to_analyze = [
                    m for m in self._metrics_buffer
                    if m.timestamp >= since
                ]
            elif window_size:
                # Custom window size: last N trades
                metrics_to_analyze = list(self._metrics_buffer)[-window_size:]
            else:
                # Default: all trades in buffer (up to window_size)
                metrics_to_analyze = list(self._metrics_buffer)
            
            if not metrics_to_analyze:
                # Empty metrics - return zero stats
                return AggregateMetrics(
                    window_size=window_size or self.window_size,
                    total_trades=0
                )
            
            # Calculate aggregates
            total_trades = len(metrics_to_analyze)
            scalp_count = sum(1 for m in metrics_to_analyze if m.trade_type == "SCALP")
            intraday_count = sum(1 for m in metrics_to_analyze if m.trade_type == "INTRADAY")
            
            # Count overrides and defaults
            override_count = sum(
                1 for m in metrics_to_analyze
                if m.factor_used == "override"
            )
            default_fallback_count = sum(
                1 for m in metrics_to_analyze
                if m.factor_used == "default"
            )
            
            # Confidence distribution
            high_confidence_count = sum(
                1 for m in metrics_to_analyze
                if m.confidence >= 0.7
            )
            medium_confidence_count = sum(
                1 for m in metrics_to_analyze
                if 0.4 <= m.confidence < 0.7
            )
            low_confidence_count = sum(
                1 for m in metrics_to_analyze
                if m.confidence < 0.4
            )
            
            # Factor usage
            keyword_match_count = sum(
                1 for m in metrics_to_analyze
                if m.factor_used == "keyword"
            )
            stop_atr_ratio_count = sum(
                1 for m in metrics_to_analyze
                if m.factor_used == "stop_atr_ratio"
            )
            session_strategy_count = sum(
                1 for m in metrics_to_analyze
                if m.factor_used == "session_strategy"
            )
            override_count_factor = sum(
                1 for m in metrics_to_analyze
                if m.factor_used == "override"
            )
            default_fallback_count_factor = sum(
                1 for m in metrics_to_analyze
                if m.factor_used == "default"
            )
            
            # Performance metrics
            latencies = [m.latency_ms for m in metrics_to_analyze]
            total_latency_ms = sum(latencies)
            max_latency_ms = max(latencies) if latencies else 0.0
            timeout_count = sum(
                1 for m in metrics_to_analyze
                if m.latency_ms > 500.0  # Timeout threshold: 500ms
            )
            
            # Timestamps
            first_trade_time = min(m.timestamp for m in metrics_to_analyze)
            last_trade_time = max(m.timestamp for m in metrics_to_analyze)
            
            aggregate = AggregateMetrics(
                window_size=window_size or self.window_size,
                total_trades=total_trades,
                scalp_count=scalp_count,
                intraday_count=intraday_count,
                override_count=override_count,
                default_fallback_count=default_fallback_count,
                high_confidence_count=high_confidence_count,
                medium_confidence_count=medium_confidence_count,
                low_confidence_count=low_confidence_count,
                keyword_match_count=keyword_match_count,
                stop_atr_ratio_count=stop_atr_ratio_count,
                session_strategy_count=session_strategy_count,
                override_count_factor=override_count_factor,
                default_fallback_count_factor=default_fallback_count_factor,
                total_latency_ms=total_latency_ms,
                max_latency_ms=max_latency_ms,
                timeout_count=timeout_count,
                first_trade_time=first_trade_time,
                last_trade_time=last_trade_time
            )
            
            # Cache result (if no filters applied)
            if not window_size and not since:
                self._aggregate_cache = aggregate
                self._cache_valid = True
            
            return aggregate
    
    def format_log_summary(self, metrics: Optional[AggregateMetrics] = None) -> str:
        """
        Format aggregate metrics as a log summary string.
        
        Args:
            metrics: Optional AggregateMetrics (if None, calculates from current window)
        
        Returns:
            Formatted summary string for logging
        """
        if metrics is None:
            metrics = self.get_aggregate_metrics()
        
        if metrics.total_trades == 0:
            return (
                "📊 Classification Metrics Summary (Last 100 Trades)\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "No trades classified yet."
            )
        
        # Calculate percentages
        scalp_pct = (metrics.scalp_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        intraday_pct = (metrics.intraday_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        
        high_conf_pct = (metrics.high_confidence_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        medium_conf_pct = (metrics.medium_confidence_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        low_conf_pct = (metrics.low_confidence_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        
        keyword_pct = (metrics.keyword_match_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        stop_atr_pct = (metrics.stop_atr_ratio_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        session_pct = (metrics.session_strategy_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        
        avg_latency = (metrics.total_latency_ms / metrics.total_trades) if metrics.total_trades > 0 else 0.0
        
        summary = (
            f"📊 Classification Metrics Summary (Last {metrics.window_size} Trades)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"🔢 Total Trades: {metrics.total_trades}\n"
            f"\n"
            f"📊 Classification Breakdown:\n"
            f"   🟢 SCALP: {metrics.scalp_count} trades ({scalp_pct:.0f}%)\n"
            f"   🔵 INTRADAY: {metrics.intraday_count} trades ({intraday_pct:.0f}%)\n"
        )
        
        if metrics.override_count > 0:
            override_pct = (metrics.override_count / metrics.total_trades * 100)
            summary += f"   ⚙️ OVERRIDE: {metrics.override_count} trades ({override_pct:.0f}%)\n"
        
        summary += (
            f"\n"
            f"🎯 Confidence Levels:\n"
            f"   ✅ HIGH (≥0.7): {metrics.high_confidence_count} trades ({high_conf_pct:.0f}%)\n"
            f"   ⚠️ MEDIUM (0.4-0.69): {metrics.medium_confidence_count} trades ({medium_conf_pct:.0f}%)\n"
            f"   ❌ LOW (<0.4): {metrics.low_confidence_count} trades ({low_conf_pct:.0f}%) → defaulted to INTRADAY\n"
            f"\n"
            f"🔍 Classification Factors:\n"
            f"   • Keyword Match: {metrics.keyword_match_count} trades ({keyword_pct:.0f}%)\n"
            f"   • Stop/ATR Ratio: {metrics.stop_atr_ratio_count} trades ({stop_atr_pct:.0f}%)\n"
            f"   • Session Strategy: {metrics.session_strategy_count} trades ({session_pct:.0f}%)\n"
        )
        
        if metrics.default_fallback_count > 0:
            default_pct = (metrics.default_fallback_count / metrics.total_trades * 100)
            summary += f"   • Default Fallback: {metrics.default_fallback_count} trades ({default_pct:.0f}%)\n"
        
        summary += (
            f"\n"
            f"⚡ Performance:\n"
            f"   • Avg Classification Latency: {avg_latency:.0f}ms\n"
            f"   • Max Latency: {metrics.max_latency_ms:.0f}ms\n"
            f"   • Timeouts (fallback): {metrics.timeout_count}\n"
        )
        
        if metrics.first_trade_time and metrics.last_trade_time:
            duration = metrics.last_trade_time - metrics.first_trade_time
            summary += f"\n⏰ Window: {metrics.first_trade_time.strftime('%Y-%m-%d %H:%M')} to {metrics.last_trade_time.strftime('%Y-%m-%d %H:%M')} ({duration.days}d {duration.seconds//3600}h)\n"
        
        return summary
    
    def format_discord_daily_summary(self) -> str:
        """
        Format metrics as Discord daily summary message (last 24 hours).
        
        Returns:
            Formatted Discord message string
        """
        since = datetime.utcnow() - timedelta(hours=24)
        metrics = self.get_aggregate_metrics(since=since)
        
        if metrics.total_trades == 0:
            return (
                "📊 **Trade Classification Metrics - Daily Summary**\n\n"
                f"📅 Date: {datetime.utcnow().strftime('%Y-%m-%d')}\n"
                "🔢 Total Trades (Last 24h): 0\n\n"
                "No trades classified in the last 24 hours."
            )
        
        # Calculate percentages
        scalp_pct = (metrics.scalp_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        intraday_pct = (metrics.intraday_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        
        high_conf_pct = (metrics.high_confidence_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        medium_conf_pct = (metrics.medium_confidence_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        low_conf_pct = (metrics.low_confidence_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        
        keyword_pct = (metrics.keyword_match_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        stop_atr_pct = (metrics.stop_atr_ratio_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        session_pct = (metrics.session_strategy_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        
        avg_latency = (metrics.total_latency_ms / metrics.total_trades) if metrics.total_trades > 0 else 0.0
        
        message = (
            "📊 **Trade Classification Metrics - Daily Summary**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📅 Date: {datetime.utcnow().strftime('%Y-%m-%d')}\n"
            f"🔢 Total Trades (Last 24h): {metrics.total_trades}\n\n"
            f"📊 **Classification Breakdown:**\n"
            f"   🟢 SCALP: {metrics.scalp_count} trades ({scalp_pct:.0f}%)\n"
            f"   🔵 INTRADAY: {metrics.intraday_count} trades ({intraday_pct:.0f}%)\n\n"
            f"🎯 **Confidence Levels:**\n"
            f"   ✅ HIGH (≥0.7): {metrics.high_confidence_count} trades ({high_conf_pct:.0f}%)\n"
            f"   ⚠️ MEDIUM (0.4-0.69): {metrics.medium_confidence_count} trades ({medium_conf_pct:.0f}%)\n"
            f"   ❌ LOW (<0.4): {metrics.low_confidence_count} trades ({low_conf_pct:.0f}%) → defaulted to INTRADAY\n\n"
            f"🔍 **Classification Factors:**\n"
            f"   • Keyword Match: {metrics.keyword_match_count} trades ({keyword_pct:.0f}%)\n"
            f"   • Stop/ATR Ratio: {metrics.stop_atr_ratio_count} trades ({stop_atr_pct:.0f}%)\n"
            f"   • Session Strategy: {metrics.session_strategy_count} trades ({session_pct:.0f}%)\n\n"
            f"⚡ **Performance:**\n"
            f"   • Avg Latency: {avg_latency:.0f}ms\n"
            f"   • Max Latency: {metrics.max_latency_ms:.0f}ms\n"
            f"   • Timeouts: {metrics.timeout_count}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        return message
    
    def format_discord_weekly_summary(self) -> str:
        """
        Format metrics as Discord weekly summary message (last 7 days).
        
        Returns:
            Formatted Discord message string
        """
        since = datetime.utcnow() - timedelta(days=7)
        metrics = self.get_aggregate_metrics(since=since)
        
        if metrics.total_trades == 0:
            return (
                "📊 **Trade Classification Metrics - Weekly Summary**\n\n"
                f"📈 Period: {(datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')} to {datetime.utcnow().strftime('%Y-%m-%d')} (7 days)\n"
                "🔢 Total Trades: 0\n\n"
                "No trades classified in the last 7 days."
            )
        
        # Calculate percentages
        scalp_pct = (metrics.scalp_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        intraday_pct = (metrics.intraday_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        
        high_conf_pct = (metrics.high_confidence_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        medium_conf_pct = (metrics.medium_confidence_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        low_conf_pct = (metrics.low_confidence_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        
        keyword_pct = (metrics.keyword_match_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        stop_atr_pct = (metrics.stop_atr_ratio_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        session_pct = (metrics.session_strategy_count / metrics.total_trades * 100) if metrics.total_trades > 0 else 0.0
        
        avg_latency = (metrics.total_latency_ms / metrics.total_trades) if metrics.total_trades > 0 else 0.0
        
        period_start = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        period_end = datetime.utcnow().strftime('%Y-%m-%d')
        
        message = (
            "📊 **Trade Classification Metrics - Weekly Summary**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📈 Period: {period_start} to {period_end} (7 days)\n"
            f"🔢 Total Trades: {metrics.total_trades}\n\n"
            f"📊 **Classification Breakdown:**\n"
            f"   🟢 SCALP: {metrics.scalp_count} trades ({scalp_pct:.0f}%)\n"
            f"   🔵 INTRADAY: {metrics.intraday_count} trades ({intraday_pct:.0f}%)\n"
        )
        
        if metrics.override_count > 0:
            override_pct = (metrics.override_count / metrics.total_trades * 100)
            message += f"   ⚙️ OVERRIDE: {metrics.override_count} trades ({override_pct:.0f}%)\n"
        
        message += (
            f"\n🎯 **Confidence Levels:**\n"
            f"   ✅ HIGH (≥0.7): {metrics.high_confidence_count} trades ({high_conf_pct:.0f}%)\n"
            f"   ⚠️ MEDIUM (0.4-0.69): {metrics.medium_confidence_count} trades ({medium_conf_pct:.0f}%)\n"
            f"   ❌ LOW (<0.4): {metrics.low_confidence_count} trades ({low_conf_pct:.0f}%) → defaulted to INTRADAY\n\n"
            f"🔍 **Classification Factors:**\n"
            f"   • Keyword Match: {metrics.keyword_match_count} trades ({keyword_pct:.0f}%)\n"
            f"   • Stop/ATR Ratio: {metrics.stop_atr_ratio_count} trades ({stop_atr_pct:.0f}%)\n"
            f"   • Session Strategy: {metrics.session_strategy_count} trades ({session_pct:.0f}%)\n"
        )
        
        if metrics.default_fallback_count > 0:
            default_pct = (metrics.default_fallback_count / metrics.total_trades * 100)
            message += f"   • Default Fallback: {metrics.default_fallback_count} trades ({default_pct:.0f}%)\n"
        
        message += (
            f"\n⚡ **Performance:**\n"
            f"   • Avg Latency: {avg_latency:.0f}ms\n"
            f"   • Max Latency: {metrics.max_latency_ms:.0f}ms\n"
            f"   • Timeouts: {metrics.timeout_count}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        return message
    
    def reset(self) -> None:
        """Clear all metrics (for testing or manual reset)."""
        with self._lock:
            self._metrics_buffer.clear()
            self._aggregate_cache = None
            self._cache_valid = False
        logger.info("Classification metrics reset")


# Global singleton instance (lazy initialization)
_metrics_instance: Optional[ClassificationMetrics] = None
_metrics_lock = Lock()


def get_metrics_instance(window_size: int = 100, enabled: bool = True) -> ClassificationMetrics:
    """
    Get or create the global ClassificationMetrics singleton instance.
    
    Args:
        window_size: Window size for rolling metrics (only used on first creation)
        enabled: Whether metrics are enabled (only used on first creation)
    
    Returns:
        Global ClassificationMetrics instance
    """
    global _metrics_instance
    
    with _metrics_lock:
        if _metrics_instance is None:
            _metrics_instance = ClassificationMetrics(window_size=window_size, enabled=enabled)
        return _metrics_instance


def record_classification_metric(
    ticket: Optional[int],
    symbol: str,
    trade_type: str,
    confidence: float,
    reasoning: str,
    factor_used: str,
    latency_ms: float,
    feature_enabled: bool = True
) -> None:
    """
    Convenience function to record a classification metric.
    
    Args:
        ticket: Position ticket number
        symbol: Trading symbol
        trade_type: "SCALP" or "INTRADAY"
        confidence: Confidence score (0.0-1.0)
        reasoning: Classification reasoning string
        factor_used: Which factor determined classification
        latency_ms: Classification latency in milliseconds
        feature_enabled: Whether classification feature was enabled
    """
    metrics = get_metrics_instance()
    metrics.record_classification(
        ticket=ticket,
        symbol=symbol,
        trade_type=trade_type,
        confidence=confidence,
        reasoning=reasoning,
        factor_used=factor_used,
        latency_ms=latency_ms,
        feature_enabled=feature_enabled
    )
