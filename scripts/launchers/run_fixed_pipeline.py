#!/usr/bin/env python3
"""
Run the fixed Pipecat pipeline with custom JSON serializer
"""
import asyncio
import sys
from loguru import logger

# Add src to path
sys.path.insert(0, '/mnt/c/users/dfoss/desktop/localaimodels/assistant')

from src.core.pipecat_pipeline_fixed import LocalVoicePipelineFixed

async def main():
    """Run the fixed pipeline"""
    logger.info("🚀 Starting Fixed Pipecat Voice Pipeline...")
    
    # Create and start pipeline
    pipeline = LocalVoicePipelineFixed(host="0.0.0.0", port=8001)
    
    try:
        success = await pipeline.start()
        if not success:
            logger.error("Failed to start pipeline")
            return
            
        logger.info("✅ Pipeline is running!")
        logger.info("🌐 WebSocket server listening on ws://0.0.0.0:8001")
        logger.info("📝 Using custom JSON serializer for Discord bot compatibility")
        logger.info("")
        logger.info("Expected message format from Discord bot:")
        logger.info("  Audio: {'type': 'audio_input', 'data': '<base64>', 'sample_rate': 16000, 'channels': 1}")
        logger.info("  Text:  {'type': 'text_input', 'text': 'message'}")
        logger.info("")
        logger.info("Response format to Discord bot:")
        logger.info("  Audio: {'type': 'audio_output', 'data': '<base64>', 'sample_rate': 16000, 'channels': 1}")
        logger.info("  Text:  {'type': 'text', 'text': 'message'}")
        logger.info("")
        logger.info("Press Ctrl+C to stop...")
        
        # Keep running
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        logger.info("\n⏹️  Shutting down...")
        await pipeline.stop()
    except Exception as e:
        logger.error(f"❌ Pipeline error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())