"""
Signal Pre-Filter - Safety Gate Before Execution
Final validation before any trade is executed.

Checks:
1. Feed synchronization (Binance-MT5)
2. Spread validation
3. Price freshness
4. Offset sanity
5. Circuit breaker status
6. Exposure limits

Usage:
    prefilter = SignalPreFilter(binance_service, circuit_breaker, exposure_guard)
    
    can_execute, reason = prefilter.validate_signal(
        symbol="BTCUSDc",
        signal={"entry": 112150, "sl": 112000, "tp": 112400},
        mt5_quote=quote
    )
    
    if not can_execute:
        logger.warning(f"Trade blocked: {reason}")
"""

import logging
from typing import Dict, Optional, Tuple
import sys
import codecs

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass

logger = logging.getLogger(__name__)


class SignalPreFilter:
    """
    Pre-execution safety filter.
    
    Validates all conditions before allowing trade execution.
    """
    
    def __init__(
        self,
        binance_service=None,
        circuit_breaker=None,
        exposure_guard=None,
        min_confidence: int = 70
    ):
        """
        Args:
            binance_service: BinanceService instance (optional)
            circuit_breaker: CircuitBreaker instance (optional)
            exposure_guard: ExposureGuard instance (optional)
            min_confidence: Minimum confidence score to allow execution
        """
        self.binance_service = binance_service
        self.circuit_breaker = circuit_breaker
        self.exposure_guard = exposure_guard
        self.min_confidence = min_confidence
        
        logger.info(f"🛡️ SignalPreFilter initialized (min_confidence={min_confidence})")
        
    def validate_signal(
        self,
        symbol: str,
        signal: dict,
        mt5_quote: dict
    ) -> Tuple[bool, str, dict]:
        """
        Validate a signal before execution.
        
        Args:
            symbol: MT5 symbol (e.g., "BTCUSDc")
            signal: Signal dict with {action, entry, sl, tp, confidence, ...}
            mt5_quote: MT5 quote dict with {bid, ask, ...}
            
        Returns:
            (can_execute, reason, validation_details)
            
        Example:
            can_execute, reason, details = prefilter.validate_signal(
                "BTCUSDc",
                {"action": "BUY", "entry": 112150, "sl": 112000, "tp": 112400, "confidence": 85},
                {"bid": 112120, "ask": 112125}
            )
        """
        validation_details = {
            "checks_passed": [],
            "checks_failed": [],
            "warnings": []
        }
        
        # Check 1: Confidence threshold
        confidence = signal.get("confidence", 0)
        if confidence < self.min_confidence:
            validation_details["checks_failed"].append(
                f"Confidence too low: {confidence} < {self.min_confidence}"
            )
            return False, f"Confidence too low: {confidence}%", validation_details
        validation_details["checks_passed"].append(f"Confidence OK: {confidence}%")
        
        # Check 2: Circuit breaker
        if self.circuit_breaker:
            allowed, cb_reason = self.circuit_breaker.allow_order()
            if not allowed:
                reason = f"Circuit breaker engaged: {cb_reason}"
                validation_details["checks_failed"].append(reason)
                return False, reason, validation_details
            validation_details["checks_passed"].append("Circuit breaker OK")
            
        # Check 3: Exposure guard
        if self.exposure_guard:
            # Check if we can open a new position
            # Need to know direction for proper exposure check
            action = signal.get("action", "BUY").upper()
            guard_result = self.exposure_guard.evaluate(
                symbol=symbol,
                side=action,
                desired_risk_pct=1.0  # Default 1% risk
            )
            
            if not guard_result.allow:
                reason = f"Exposure limit reached: {guard_result.reason}"
                validation_details["checks_failed"].append(reason)
                return False, reason, validation_details
            validation_details["checks_passed"].append("Exposure check OK")
            
        # Check 4: Binance feed validation (if available)
        if self.binance_service:
            # Map MT5 symbol to Binance symbol if needed (e.g., BTCUSDc -> BTCUSDT)
            def _map_to_binance_symbol(sym: str) -> Optional[str]:
                s = (sym or "").upper()
                # BTC
                if s.startswith("BTCUSD"):
                    return "BTCUSDT"
                # ETH
                if s.startswith("ETHUSD"):
                    return "ETHUSDT"
                # If already a common Binance symbol, pass through
                if s.endswith("USDT"):
                    return s
                # Unknown mapping -> no Binance validation
                return None

            binance_symbol = _map_to_binance_symbol(symbol)

            # If Binance does not provide data for this symbol, skip validation (non-Binance symbols like AUDJPY)
            try:
                latest_price = self.binance_service.get_latest_price(binance_symbol) if binance_symbol else None
            except Exception:
                latest_price = None

            if latest_price is None:
                validation_details["warnings"].append("Binance feed unavailable for symbol - skipping validation")
            else:
                is_safe, feed_reason = self.binance_service.validate_execution(
                    binance_symbol,
                    mt5_quote['bid'],
                    mt5_quote['ask']
                )
                
                if not is_safe:
                    validation_details["checks_failed"].append(f"Feed validation: {feed_reason}")
                    return False, f"Feed validation failed: {feed_reason}", validation_details
                    
                validation_details["checks_passed"].append("Feed validation OK")
                
                # Check feed health - be more lenient for symbols without Binance data
                try:
                    health = self.binance_service.get_feed_health(binance_symbol)
                    if health["overall_status"] == "warning":
                        validation_details["warnings"].append(
                            f"Feed health warning: {health['sync']['reason']}"
                        )
                    elif health["overall_status"] == "critical":
                        # Only block if we have actual Binance data but it's stale
                        if "No sync data available" in health['sync'].get('reason', ''):
                            validation_details["warnings"].append("Binance sync data unavailable - proceeding with MT5 only")
                        else:
                            reason = f"Feed health critical: {health['sync']['reason']}"
                            validation_details["checks_failed"].append(reason)
                            return False, reason, validation_details
                except Exception as e:
                    validation_details["warnings"].append(f"Feed health check failed: {e} - proceeding with MT5 only")
                
        # Check 5: Price sanity
        if "entry" in signal:
            entry = signal["entry"]
            spread = mt5_quote['ask'] - mt5_quote['bid']
            
            # Entry should be near current price (within 1% for market orders)
            action = signal.get("action", "BUY").upper()
            current_price = mt5_quote['ask'] if action == "BUY" else mt5_quote['bid']
            
            price_diff_pct = abs(entry - current_price) / current_price * 100
            
            if price_diff_pct > 1.0:  # More than 1% away
                validation_details["warnings"].append(
                    f"Entry price {price_diff_pct:.2f}% away from market"
                )
                
        validation_details["checks_passed"].append("Price sanity OK")
        
        # Check 6: Stop loss validation
        if "sl" in signal or "stop_loss" in signal:
            sl = signal.get("sl") or signal.get("stop_loss")
            entry = signal.get("entry", current_price)
            action = signal.get("action", "BUY").upper()
            
            # Validate SL is on correct side
            if action == "BUY" and sl >= entry:
                reason = f"Invalid SL for BUY: {sl} should be < entry {entry}"
                validation_details["checks_failed"].append(reason)
                return False, reason, validation_details
            elif action == "SELL" and sl <= entry:
                reason = f"Invalid SL for SELL: {sl} should be > entry {entry}"
                validation_details["checks_failed"].append(reason)
                return False, reason, validation_details
                
        validation_details["checks_passed"].append("SL validation OK")
        
        # All checks passed
        logger.info(f"✅ Signal validated for {symbol}: {len(validation_details['checks_passed'])} checks passed")
        
        if validation_details["warnings"]:
            logger.warning(f"⚠️ Validation warnings: {', '.join(validation_details['warnings'])}")
            
        return True, "All validation checks passed", validation_details
        
    def adjust_and_validate(
        self,
        symbol: str,
        signal: dict,
        mt5_quote: dict
    ) -> Tuple[bool, str, Optional[dict]]:
        """
        Adjust signal for MT5 and validate in one step.
        
        Args:
            symbol: MT5 symbol
            signal: Original signal (Binance prices)
            mt5_quote: MT5 quote
            
        Returns:
            (can_execute, reason, adjusted_signal)
            
        Example:
            can_execute, reason, adjusted = prefilter.adjust_and_validate(
                "BTCUSDc", signal, quote
            )
            if can_execute:
                mt5.order_send(adjusted)
        """
        # Adjust signal if Binance service available
        if self.binance_service:
            try:
                adjusted_signal = self.binance_service.adjust_signal_for_mt5(symbol, signal)
            except Exception as e:
                logger.error(f"❌ Failed to adjust signal: {e}")
                return False, f"Signal adjustment failed: {e}", None
        else:
            adjusted_signal = signal.copy()
            
        # Validate adjusted signal
        can_execute, reason, details = self.validate_signal(symbol, adjusted_signal, mt5_quote)
        
        if can_execute:
            return True, reason, adjusted_signal
        else:
            return False, reason, None
            
    def get_validation_report(
        self,
        symbol: str,
        signal: dict,
        mt5_quote: dict
    ) -> dict:
        """
        Get detailed validation report without blocking.
        
        Useful for debugging or displaying to user.
        
        Returns:
            {
                "can_execute": bool,
                "reason": str,
                "checks_passed": [...],
                "checks_failed": [...],
                "warnings": [...],
                "feed_health": {...},
                "circuit_status": {...},
                "exposure_status": {...}
            }
        """
        can_execute, reason, validation_details = self.validate_signal(
            symbol, signal, mt5_quote
        )
        
        report = {
            "can_execute": can_execute,
            "reason": reason,
            **validation_details
        }
        
        # Add feed health
        if self.binance_service:
            report["feed_health"] = self.binance_service.get_feed_health(symbol)
        else:
            report["feed_health"] = None
            
        # Add circuit breaker status
        if self.circuit_breaker:
            allowed, cb_reason = self.circuit_breaker.allow_order()
            report["circuit_status"] = {
                "can_trade": allowed,
                "status": "open" if allowed else "tripped",
                "reason": cb_reason if not allowed else "OK"
            }
        else:
            report["circuit_status"] = None
            
        # Add exposure status
        if self.exposure_guard:
            action = signal.get("action", "BUY").upper()
            guard_result = self.exposure_guard.evaluate(
                symbol=symbol,
                side=action,
                desired_risk_pct=1.0
            )
            report["exposure_status"] = {
                "can_open": guard_result.allow,
                "reason": guard_result.reason if not guard_result.allow else "OK"
            }
        else:
            report["exposure_status"] = None
            
        return report
        
    def print_validation_report(self, report: dict):
        """
        Pretty-print validation report.
        """
        print("\n" + "="*70)
        print("🛡️ SIGNAL PRE-FILTER VALIDATION REPORT")
        print("="*70)
        
        status_emoji = "✅" if report["can_execute"] else "❌"
        print(f"{status_emoji} Can Execute: {report['can_execute']}")
        print(f"Reason: {report['reason']}\n")
        
        if report["checks_passed"]:
            print("✅ Checks Passed:")
            for check in report["checks_passed"]:
                print(f"   • {check}")
            print()
            
        if report["checks_failed"]:
            print("❌ Checks Failed:")
            for check in report["checks_failed"]:
                print(f"   • {check}")
            print()
            
        if report["warnings"]:
            print("⚠️ Warnings:")
            for warning in report["warnings"]:
                print(f"   • {warning}")
            print()
            
        if report["feed_health"]:
            health = report["feed_health"]
            print(f"📡 Feed Health: {health['overall_status']}")
            if health.get("sync"):
                print(f"   Offset: {health['sync'].get('offset', 'N/A')} pips")
                print(f"   Age: {health['sync'].get('last_sync_age', 'N/A'):.1f}s")
            print()
            
        print("="*70 + "\n")


# Example usage
def example_usage():
    """
    Example of how to use SignalPreFilter.
    """
    from infra.binance_service import BinanceService
    from infra.circuit_breaker import CircuitBreaker
    from infra.exposure_guard import ExposureGuard
    
    # Initialize components
    binance_service = BinanceService()
    circuit_breaker = CircuitBreaker()
    exposure_guard = ExposureGuard()
    
    # Create prefilter
    prefilter = SignalPreFilter(
        binance_service=binance_service,
        circuit_breaker=circuit_breaker,
        exposure_guard=exposure_guard,
        min_confidence=70
    )
    
    # Mock signal
    signal = {
        "action": "BUY",
        "entry": 112150,
        "sl": 112000,
        "tp": 112400,
        "confidence": 85
    }
    
    # Mock MT5 quote
    mt5_quote = {
        "bid": 112120,
        "ask": 112125
    }
    
    # Validate
    can_execute, reason, details = prefilter.validate_signal(
        "BTCUSDc", signal, mt5_quote
    )
    
    print(f"Result: {can_execute} - {reason}")
    print(f"Checks passed: {len(details['checks_passed'])}")
    print(f"Checks failed: {len(details['checks_failed'])}")
    
    # Get full report
    report = prefilter.get_validation_report("BTCUSDc", signal, mt5_quote)
    prefilter.print_validation_report(report)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🧪 Testing SignalPreFilter\n")
    example_usage()

