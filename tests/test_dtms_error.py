"""
Test DTMS Error Isolation
"""

import asyncio
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_dtms_error():
    print('🔍 Testing DTMS Error Isolation')
    print('=' * 50)
    
    try:
        # Test 1: Import DTMS integration
        print('📦 Test 1: Importing DTMS integration...')
        from dtms_unified_pipeline_integration import initialize_dtms_unified_pipeline
        print('   ✅ DTMS integration imported successfully')
        
        # Test 2: Initialize DTMS
        print('🚀 Test 2: Initializing DTMS...')
        result = await initialize_dtms_unified_pipeline()
        print(f'   → DTMS Result: {result}')
        
        if result:
            print('   ✅ DTMS initialized successfully')
        else:
            print('   ❌ DTMS initialization failed')
            
    except Exception as e:
        print(f'   ❌ DTMS Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_dtms_error())
