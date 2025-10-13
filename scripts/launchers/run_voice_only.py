#!/usr/bin/env python3
"""
Run ONLY the voice pipeline on port 8002
This runs the STT/TTS pipeline separately from the API
"""

import asyncio
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from loguru import logger

# Load environment
load_dotenv()

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {message}")

async def run_voice_pipeline():
    """Run the voice pipeline WebSocket server"""
    logger.info("🎤 Starting Voice Pipeline Server (port 8002)")
    
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
        
        # Run the server
        await handler.start_server()
        
    except Exception as e:
        logger.error(f"Failed to start voice pipeline: {e}")
        raise

if __name__ == "__main__":
    logger.info("🚀 Starting Voice Pipeline Only")
    logger.info("📝 This runs STT/TTS pipeline separately from API")
    
    try:
        asyncio.run(run_voice_pipeline())
    except KeyboardInterrupt:
        logger.info("⏹️ Voice pipeline stopped")