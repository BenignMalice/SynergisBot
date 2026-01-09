# Add Range Scalping Tool to desktop_agent.py

## ⚠️ **MANUAL STEP REQUIRED**

The tool registration needs to be added manually to `desktop_agent.py`.

## 📍 **Location**

Add the code **after line 6118** (after `tool_analyse_symbol_full` function, before `tool_execute_trade`).

## 📝 **Code to Add**

Open `desktop_agent_range_scalp_tool.py` - copy the entire file contents and paste it into `desktop_agent.py` at line 6119.

**OR** use this code:

```python
@registry.register("moneybot.analyse_range_scalp_opportunity")
async def tool_analyse_range_scalp_opportunity(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyse range scalping opportunities for a symbol.
    
    Detects session/daily/dynamic ranges, evaluates 5 range scalping strategies
    (VWAP Reversion, BB Fade, PDH/PDL Rejection, RSI Bounce, Liquidity Sweep),
    and applies weighted 3-confluence risk filtering.
    
    Args:
        symbol: Trading symbol (e.g., BTCUSD, XAUUSD)
        strategy_filter: Optional strategy name to focus on
        check_risk_filters: Whether to apply risk mitigation (default: true)
    
    Returns:
        Analysis with range structure, risk checks, top strategy, warnings
    """
    symbol = args.get("symbol")
    if not symbol:
        raise ValueError("Missing required argument: symbol")
    
    strategy_filter = args.get("strategy_filter")
    check_risk_filters = args.get("check_risk_filters", True)
    
    logger.info(f"📊 Analysing range scalping opportunity for {symbol}...")
    
    try:
        # Normalize symbol
        symbol_normalized = symbol if symbol.endswith('c') else f"{symbol}c"
        
        # Initialize services
        from infra.range_scalping_analysis import analyse_range_scalp_opportunity
        from infra.indicator_bridge import IndicatorBridge
        from infra.feature_builder_advanced import build_features_advanced
        
        mt5_service = registry.mt5_service
        if not mt5_service:
            raise RuntimeError("MT5 service not initialized")
        
        bridge = IndicatorBridge()
        
        # Fetch multi-timeframe data for indicators
        all_timeframe_data = bridge.get_multi(symbol_normalized)
        m5_data = all_timeframe_data.get("M5")
        m15_data = all_timeframe_data.get("M15")
        h1_data = all_timeframe_data.get("H1")
        
        if not all([m5_data, m15_data, h1_data]):
            raise RuntimeError(f"Failed to fetch market data for {symbol_normalized}")
        
        # Get current price
        tick = mt5_service.get_tick(symbol_normalized)
        current_price = tick.bid if tick else 0
        
        # Prepare indicators
        indicators = {
            "rsi": m5_data.get("indicators", {}).get("rsi", 50),
            "bb_upper": m5_data.get("indicators", {}).get("bb_upper"),
            "bb_lower": m5_data.get("indicators", {}).get("bb_lower"),
            "bb_middle": m5_data.get("indicators", {}).get("bb_middle"),
            "stoch_k": m5_data.get("indicators", {}).get("stoch_k", 50),
            "stoch_d": m5_data.get("indicators", {}).get("stoch_d", 50),
            "adx_h1": h1_data.get("indicators", {}).get("adx", 20),
            "atr_5m": m5_data.get("indicators", {}).get("atr14", 0)
        }
        
        # Prepare market data
        # Get PDH/PDL from advanced features if available
        pdh = None
        pdl = None
        vwap = None
        
        try:
            advanced_features = build_features_advanced(
                symbol=symbol_normalized,
                df_m5=m5_data.get("df"),
                df_m15=m15_data.get("df"),
                df_h1=h1_data.get("df"),
                current_price=current_price
            )
            
            if advanced_features and "features" in advanced_features:
                m15_features = advanced_features["features"].get("M15", {})
                liquidity = m15_features.get("liquidity", {})
                pdh = liquidity.get("pdh")
                pdl = liquidity.get("pdl")
                
                vwap_data = m15_features.get("vwap")
                if vwap_data:
                    vwap = vwap_data.get("value")
        except Exception as e:
            logger.debug(f"Could not fetch PDH/PDL/VWAP: {e}")
        
        # Get volume data
        volume_current = 0
        volume_1h_avg = 0
        if m5_data.get("df") is not None:
            try:
                df_m5 = m5_data["df"]
                if hasattr(df_m5, "iloc") and len(df_m5) > 0:
                    volume_current = float(df_m5.iloc[-1].get("tick_volume", 0))
                    volume_1h_avg = float(df_m5.iloc[-12:]["tick_volume"].mean()) if len(df_m5) >= 12 else volume_current
            except:
                pass
        
        # Get recent candles
        recent_candles = []
        if m5_data.get("df") is not None:
            try:
                df_m5 = m5_data["df"]
                if hasattr(df_m5, "iloc"):
                    for i in range(max(0, len(df_m5) - 5), len(df_m5)):
                        recent_candles.append({
                            "open": float(df_m5.iloc[i]["open"]),
                            "high": float(df_m5.iloc[i]["high"]),
                            "low": float(df_m5.iloc[i]["low"]),
                            "close": float(df_m5.iloc[i]["close"]),
                            "volume": int(df_m5.iloc[i].get("tick_volume", 0))
                        })
            except:
                pass
        
        # Prepare market_data dict
        market_data = {
            "current_price": current_price,
            "vwap": vwap,
            "atr": indicators.get("atr_5m", 0),
            "atr_5m": indicators.get("atr_5m", 0),
            "bb_width": (indicators.get("bb_upper", current_price) - indicators.get("bb_lower", current_price)) / current_price if current_price > 0 else 0,
            "pdh": pdh,
            "pdl": pdl,
            "volume_current": volume_current,
            "volume_1h_avg": volume_1h_avg,
            "recent_candles": recent_candles,
            "order_flow": {
                "signal": "NEUTRAL",
                "confidence": 0
            }
        }
        
        # Call analysis function
        result = await analyse_range_scalp_opportunity(
            symbol=symbol_normalized,
            strategy_filter=strategy_filter,
            check_risk_filters=check_risk_filters,
            market_data=market_data,
            indicators=indicators
        )
        
        logger.info(f"✅ Range scalping analysis complete for {symbol_normalized}")
        
        return {
            "summary": f"Range scalping analysis for {symbol}",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"❌ Range scalping analysis failed: {e}", exc_info=True)
        raise RuntimeError(f"Range scalping analysis failed: {str(e)}")
```

## ✅ **Verification**

After adding the code, verify it's registered:

```python
# In Python console after starting desktop_agent
from desktop_agent import registry
print("moneybot.analyse_range_scalp_opportunity" in registry.tools)
# Should print: True
```

## 🧪 **Testing**

Once added, test via ChatGPT or API:

```json
{
  "tool": "moneybot.analyse_range_scalp_opportunity",
  "arguments": {
    "symbol": "BTCUSD",
    "check_risk_filters": true
  }
}
```

