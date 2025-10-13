#!/usr/bin/env python3
"""Test the robust pipeline startup process"""

import asyncio
import logging

# Set up logging  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_pipeline_startup():
    """Test the robust pipeline startup"""
    
    logger.info("🔍 Testing robust pipeline startup...")
    
    try:
        # Import the robust pipeline
        from src.core.robust_pipecat_pipeline import RobustWebSocketWrapper
        logger.info("✅ Imported RobustWebSocketWrapper")
        
        # Create an instance
        wrapper = RobustWebSocketWrapper(host="0.0.0.0", port=8003)  # Different port to avoid conflicts
        logger.info("✅ Created RobustWebSocketWrapper instance")
        
        # Try to start it
        logger.info("🚀 Starting pipeline...")
        result = await wrapper.start()
        logger.info(f"✅ Pipeline start returned: {result}")
        
        # Wait a bit to see if the background task runs
        logger.info("⏳ Waiting 5 seconds to see background task activity...")
        await asyncio.sleep(5)
        
        # Check if it's running
        logger.info(f"📊 Pipeline is_running: {wrapper.is_running}")
        
        # Stop it
        logger.info("🛑 Stopping pipeline...")
        await wrapper.stop()
        logger.info("✅ Pipeline stopped")
        
    except Exception as e:
        logger.error(f"❌ Pipeline startup failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_pipeline_startup())