"""
Feed Validator - Safety Checks for Trade Execution
Validates feed quality and detects dangerous conditions.

Prevents trading when:
- Binance-MT5 offset too large (>100 pips)
- Broker spread too wide (>3x normal)
- Feed divergence detected (candles don't match)
- Data staleness (>60 seconds)

Usage:
    validator = FeedValidator(max_offset=100, max_spread_multiplier=3.0)
    is_safe, reason = validator.validate_execution_safety(
        symbol="BTCUSDT",
        binance_price=112180,
        mt5_bid=112120,
        mt5_ask=112125,
        offset=60
    )
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


class FeedValidator:
    """
    Validate feed quality and detect dangerous trading conditions.
    
    Safety-first approach: Block trades when data quality is questionable.
    """
    
    def __init__(
        self,
        max_offset: float = 100.0,
        max_spread_multiplier: float = 3.0,
        max_divergence_pct: float = 5.0
    ):
        """
        Args:
            max_offset: Maximum acceptable offset in pips (default: 100)
            max_spread_multiplier: Max spread vs baseline (default: 3x)
            max_divergence_pct: Max feed divergence percentage (default: 5%)
        """
        self.max_offset = max_offset
        self.max_spread_multiplier = max_spread_multiplier
        self.max_divergence_pct = max_divergence_pct
        self.baseline_spreads: Dict[str, float] = {}  # symbol -> typical spread
        
        logger.info(f"🛡️ FeedValidator initialized (max_offset={max_offset}, max_spread={max_spread_multiplier}x)")
        
    def validate_execution_safety(
        self,
        symbol: str,
        binance_price: float,
        mt5_bid: float,
        mt5_ask: float,
        offset: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Check if it's safe to execute a trade.
        
        Args:
            symbol: Trading symbol
            binance_price: Current Binance price
            mt5_bid: MT5 broker bid price
            mt5_ask: MT5 broker ask price
            offset: Known price offset (optional)
            
        Returns:
            (is_safe, reason)
            
        Example:
            is_safe, reason = validator.validate_execution_safety(
                "BTCUSDT", 112180, 112120, 112125, offset=60
            )
            if not is_safe:
                print(f"⚠️ Trade blocked: {reason}")
        """
        symbol = symbol.upper()
        
        # Check 1: Price offset
        if offset is not None and abs(offset) > self.max_offset:
            return False, f"Price offset too large: {offset:.2f} pips (max {self.max_offset})"
            
        # Check 2: Spread validation
        current_spread = mt5_ask - mt5_bid
        
        if current_spread < 0:
            return False, f"Invalid spread: bid={mt5_bid}, ask={mt5_ask} (ask < bid)"
            
        if symbol in self.baseline_spreads:
            baseline = self.baseline_spreads[symbol]
            if current_spread > baseline * self.max_spread_multiplier:
                return False, (
                    f"Spread too wide: {current_spread:.2f} "
                    f"(normal: {baseline:.2f}, max: {baseline * self.max_spread_multiplier:.2f})"
                )
        else:
            # Learn baseline spread
            self.baseline_spreads[symbol] = current_spread
            logger.info(f"📊 Learned baseline spread for {symbol}: {current_spread:.2f}")
            
        # Check 3: Feed divergence
        mt5_mid = (mt5_bid + mt5_ask) / 2
        divergence = abs(binance_price - mt5_mid)
        divergence_pct = (divergence / binance_price) * 100
        
        if divergence_pct > self.max_divergence_pct:
            return False, (
                f"Feed divergence detected: {divergence_pct:.2f}% "
                f"(Binance: {binance_price:.2f}, MT5 mid: {mt5_mid:.2f})"
            )
            
        return True, "All safety checks passed"
        
    def validate_candle_sync(
        self,
        binance_candle: dict,
        mt5_candle: dict,
        tolerance_pct: float = None
    ) -> Tuple[bool, str]:
        """
        Compare Binance and MT5 candles to detect feed issues.
        
        Args:
            binance_candle: {"open": ..., "high": ..., "low": ..., "close": ...}
            mt5_candle: same format
            tolerance_pct: Max allowed difference % (defaults to self.max_divergence_pct)
            
        Returns:
            (is_synced, reason)
            
        Example:
            is_synced, reason = validator.validate_candle_sync(
                {"open": 112100, "high": 112200, "low": 112050, "close": 112150},
                {"open": 112050, "high": 112150, "low": 112000, "close": 112100}
            )
        """
        if tolerance_pct is None:
            tolerance_pct = self.max_divergence_pct
            
        for field in ["open", "high", "low", "close"]:
            b_val = binance_candle.get(field)
            mt5_val = mt5_candle.get(field)
            
            if b_val is None or mt5_val is None:
                return False, f"Missing {field} value in candle data"
                
            diff_pct = abs(b_val - mt5_val) / b_val * 100
            
            if diff_pct > tolerance_pct:
                return False, (
                    f"Candle {field} mismatch: {diff_pct:.2f}% "
                    f"(Binance: {b_val:.2f}, MT5: {mt5_val:.2f})"
                )
                
        return True, "Candles synchronized"
        
    def validate_data_freshness(
        self,
        binance_age_seconds: float,
        mt5_age_seconds: float,
        max_age_seconds: float = 60.0
    ) -> Tuple[bool, str]:
        """
        Check if data is fresh enough for trading.
        
        Args:
            binance_age_seconds: Age of Binance data in seconds
            mt5_age_seconds: Age of MT5 data in seconds
            max_age_seconds: Maximum acceptable age
            
        Returns:
            (is_fresh, reason)
        """
        if binance_age_seconds > max_age_seconds:
            return False, f"Binance data is stale: {binance_age_seconds:.1f}s old (max {max_age_seconds}s)"
            
        if mt5_age_seconds > max_age_seconds:
            return False, f"MT5 data is stale: {mt5_age_seconds:.1f}s old (max {max_age_seconds}s)"
            
        return True, "Data is fresh"
        
    def validate_comprehensive(
        self,
        symbol: str,
        binance_price: float,
        binance_age: float,
        mt5_bid: float,
        mt5_ask: float,
        mt5_age: float,
        offset: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Run all validation checks at once.
        
        Returns:
            (is_safe, reason) - reason explains first failed check or "All checks passed"
        """
        # Check 1: Data freshness
        is_fresh, reason = self.validate_data_freshness(binance_age, mt5_age)
        if not is_fresh:
            return False, reason
            
        # Check 2: Execution safety
        is_safe, reason = self.validate_execution_safety(
            symbol, binance_price, mt5_bid, mt5_ask, offset
        )
        if not is_safe:
            return False, reason
            
        return True, "All comprehensive checks passed"
        
    def get_safety_score(
        self,
        symbol: str,
        binance_price: float,
        mt5_bid: float,
        mt5_ask: float,
        offset: Optional[float] = None
    ) -> int:
        """
        Calculate a safety score (0-100) for a trade setup.
        
        Higher score = safer to execute.
        
        Returns:
            0-100 (100 = perfectly safe, 0 = extremely unsafe)
        """
        score = 100
        
        # Deduct points for large offset
        if offset is not None:
            offset_pct = (abs(offset) / self.max_offset) * 100
            score -= min(offset_pct * 0.5, 30)  # Max 30 point deduction
            
        # Deduct points for wide spread
        current_spread = mt5_ask - mt5_bid
        if symbol in self.baseline_spreads:
            spread_ratio = current_spread / self.baseline_spreads[symbol]
            if spread_ratio > 1:
                spread_penalty = (spread_ratio - 1) * 20
                score -= min(spread_penalty, 30)  # Max 30 point deduction
                
        # Deduct points for divergence
        mt5_mid = (mt5_bid + mt5_ask) / 2
        divergence_pct = abs(binance_price - mt5_mid) / binance_price * 100
        divergence_penalty = (divergence_pct / self.max_divergence_pct) * 40
        score -= min(divergence_penalty, 40)  # Max 40 point deduction
        
        return max(0, int(score))
        
    def reset_baselines(self):
        """
        Clear learned baseline spreads.
        Useful after broker changes or market condition shifts.
        """
        self.baseline_spreads.clear()
        logger.info("🗑️ Reset all baseline spreads")
        
    def print_summary(self):
        """
        Print validator configuration and learned baselines.
        """
        print("\n" + "="*60)
        print("🛡️ FEED VALIDATOR SUMMARY")
        print("="*60)
        print(f"Max Offset: {self.max_offset} pips")
        print(f"Max Spread Multiplier: {self.max_spread_multiplier}x")
        print(f"Max Divergence: {self.max_divergence_pct}%")
        print(f"\nLearned Baseline Spreads:")
        
        if self.baseline_spreads:
            for symbol in sorted(self.baseline_spreads.keys()):
                print(f"  {symbol:12s}: {self.baseline_spreads[symbol]:.2f}")
        else:
            print("  (none yet)")
            
        print("="*60 + "\n")


# Example usage
def example_usage():
    """
    Example of how to use FeedValidator.
    """
    validator = FeedValidator(max_offset=100, max_spread_multiplier=3.0)
    
    # Test 1: Safe execution
    is_safe, reason = validator.validate_execution_safety(
        symbol="BTCUSDT",
        binance_price=112180,
        mt5_bid=112120,
        mt5_ask=112125,
        offset=60
    )
    print(f"Test 1: {is_safe} - {reason}")
    
    # Test 2: Unsafe (large offset)
    is_safe, reason = validator.validate_execution_safety(
        symbol="BTCUSDT",
        binance_price=112300,
        mt5_bid=112120,
        mt5_ask=112125,
        offset=180
    )
    print(f"Test 2: {is_safe} - {reason}")
    
    # Test 3: Candle sync
    is_synced, reason = validator.validate_candle_sync(
        {"open": 112100, "high": 112200, "low": 112050, "close": 112150},
        {"open": 112090, "high": 112190, "low": 112040, "close": 112140}
    )
    print(f"Test 3: {is_synced} - {reason}")
    
    # Test 4: Safety score
    score = validator.get_safety_score(
        "BTCUSDT", 112180, 112120, 112125, offset=60
    )
    print(f"Test 4: Safety Score = {score}/100")
    
    validator.print_summary()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🧪 Testing FeedValidator\n")
    example_usage()



