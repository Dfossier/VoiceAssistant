#!/usr/bin/env python3
"""
Test script for the robust pipeline implementation
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.core.robust_pipecat_pipeline import robust_voice_pipeline

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

async def test_robust_pipeline():
    """Test the robust pipeline startup and basic functionality"""
    logger.info("🧪 Testing Robust Pipecat Pipeline...")
    
    try:
        # Start the robust pipeline
        logger.info("▶️ Starting robust pipeline...")
        success = await robust_voice_pipeline.start()
        
        if success:
            logger.info("✅ Robust pipeline started successfully!")
            logger.info("🔄 Pipeline is now running with auto-recovery...")
            logger.info("📡 WebSocket server should be available on ws://0.0.0.0:8001")
            
            # Let it run for a bit to test stability
            logger.info("⏳ Testing pipeline stability for 30 seconds...")
            await asyncio.sleep(30)
            
            # Stop the pipeline
            logger.info("🛑 Stopping robust pipeline...")
            await robust_voice_pipeline.stop()
            logger.info("✅ Pipeline stopped gracefully")
            
        else:
            logger.error("❌ Failed to start robust pipeline")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return False
    
    logger.info("🎉 Robust pipeline test completed successfully!")
    return True

if __name__ == "__main__":
    asyncio.run(test_robust_pipeline())