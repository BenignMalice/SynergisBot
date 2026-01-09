"""
Test Unified Tick Pipeline Implementation
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone

# Add the current directory to Python path
sys.path.append('.')

from unified_tick_pipeline import UnifiedTickPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def test_unified_tick_pipeline():
    """Test the Unified Tick Pipeline"""
    try:
        logger.info("🧪 Testing Unified Tick Pipeline...")
        
        # Create pipeline instance
        pipeline = UnifiedTickPipeline()
        
        # Test initialization
        logger.info("🔧 Testing pipeline initialization...")
        success = await pipeline.start_pipeline()
        
        if success:
            logger.info("✅ Pipeline started successfully")
            
            # Test status
            status = await pipeline.get_status()
            logger.info(f"📊 Pipeline status: {status}")
            
            # Test market state
            market_state = await pipeline.get_current_market_state()
            if market_state:
                logger.info(f"📈 Market state: {market_state}")
            else:
                logger.info("📈 No market state available yet")
            
            # Test multi-timeframe data
            multi_tf_data = await pipeline.get_multi_timeframe_data("BTCUSD")
            logger.info(f"📊 Multi-timeframe data for BTCUSD: {len(multi_tf_data.get('M1', []))} M1 ticks")
            
            # Stop pipeline
            await pipeline.stop_pipeline()
            logger.info("✅ Pipeline stopped successfully")
            
        else:
            logger.error("❌ Failed to start pipeline")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

async def test_components():
    """Test individual components"""
    try:
        logger.info("🧪 Testing individual components...")
        
        # Test Binance feeds
        from unified_tick_pipeline.core.binance_feeds import BinanceFeedManager
        
        binance_config = {
            'symbols': ['BTCUSD', 'XAUUSD'],
            'primary_ws_url': 'wss://stream.binance.com/ws/',
            'mirror_ws_url': 'wss://data-stream.binance.vision/ws/',
            'heartbeat_interval': 60,
            'reconnect_delay': 5,
            'max_reconnect_attempts': 3
        }
        
        binance_feeds = BinanceFeedManager(binance_config)
        await binance_feeds.initialize()
        logger.info("✅ Binance feeds initialized")
        
        # Test MT5 bridge
        from unified_tick_pipeline.core.mt5_bridge import MT5LocalBridge
        
        mt5_config = {
            'timeout': 5000,
            'symbols': ['EURUSD', 'USDJPY'],
            'timeframes': ['M1', 'M5', 'M15'],
            'update_interval': 1000
        }
        
        mt5_bridge = MT5LocalBridge(mt5_config)
        await mt5_bridge.initialize()
        logger.info("✅ MT5 bridge initialized")
        
        # Test offset calibrator
        from unified_tick_pipeline.core.offset_calibrator import OffsetCalibrator
        
        offset_config = {
            'calibration_interval': 60,
            'atr_threshold': 0.5,
            'max_offset': 10.0,
            'drift_threshold': 2.0,
            'm5_structure_weight': 0.3,
            'min_samples_for_calibration': 3,
            'time_alignment_window': 30
        }
        
        offset_calibrator = OffsetCalibrator(offset_config)
        await offset_calibrator.initialize()
        logger.info("✅ Offset calibrator initialized")
        
        # Test data retention
        from unified_tick_pipeline.core.data_retention import DataRetentionSystem
        
        retention_config = {
            'tick_buffer_size': 1000,
            'compression_threshold': 500,
            'retention_hours': 24,
            'archive_format': 'json'
        }
        
        data_retention = DataRetentionSystem(retention_config)
        await data_retention.initialize()
        logger.info("✅ Data retention system initialized")
        
        logger.info("✅ All components tested successfully")
        
    except Exception as e:
        logger.error(f"❌ Component test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Starting Unified Tick Pipeline Tests")
    print("=" * 50)
    
    # Run tests
    asyncio.run(test_components())
    print()
    asyncio.run(test_unified_tick_pipeline())
    
    print("=" * 50)
    print("✅ Tests completed")
