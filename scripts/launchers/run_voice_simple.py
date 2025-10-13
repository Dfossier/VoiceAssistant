#!/usr/bin/env python3
"""
Simplified voice pipeline that bypasses Kokoro TTS issues
"""

import asyncio
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from loguru import logger
import os

# Load environment
load_dotenv()

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {message}")

# Disable Kokoro to bypass pip install issue
os.environ['DISABLE_KOKORO'] = '1'

async def run_voice_pipeline():
    """Run the voice pipeline WebSocket server"""
    logger.info("🎤 Starting Simplified Voice Pipeline Server (port 8002)")
    logger.info("⚠️  Kokoro TTS disabled to bypass installation issues")
    
    try:
        # Initialize local models first
        from src.core.local_models import local_model_manager
        await local_model_manager.initialize()
        
        # Import and start the enhanced WebSocket handler
        from src.core.enhanced_websocket_handler import EnhancedAudioWebSocketHandler
        
        # Create and start handler
        handler = EnhancedAudioWebSocketHandler(host="0.0.0.0", port=8002)
        
        logger.info("✅ Voice pipeline ready on ws://localhost:8002")
        logger.info("🔧 Discord bot should connect to this endpoint")
        logger.info("⚠️  TTS will use fallback (espeak) instead of Kokoro")
        
        # Run the server
        await handler.start_server()
        
    except Exception as e:
        logger.error(f"Failed to start voice pipeline: {e}")
        raise

if __name__ == "__main__":
    logger.info("🚀 Starting Simplified Voice Pipeline")
    logger.info("📝 This version bypasses Kokoro TTS installation issues")
    
    try:
        asyncio.run(run_voice_pipeline())
    except KeyboardInterrupt:
        logger.info("⏹️ Voice pipeline stopped")