#!/usr/bin/env python3
"""
Start Enhanced WebSocket Handler Service on port 8002
Based on CLAUDE.md documentation requirements
"""

import asyncio
import websockets
import logging
import json
from pathlib import Path
import sys

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.enhanced_websocket_handler import EnhancedAudioWebSocketHandler
from loguru import logger

async def main():
    """Start the WebSocket service"""
    logger.info("🎤 Starting Enhanced WebSocket Handler on port 8002")
    logger.info("📡 Listening for Discord bot connections...")
    
    # Create and initialize the enhanced handler with full pipeline
    # Use 127.0.0.1 for better Windows WSL2 compatibility
    handler = EnhancedAudioWebSocketHandler(host="127.0.0.1", port=8002)
    logger.info(f"🔧 WebSocket handler created with host: {handler.host}, port: {handler.port}")
    
    logger.info("🔄 Initializing handler components...")
    initialized = await handler.initialize()
    if not initialized:
        logger.error("❌ Failed to initialize handler")
        sys.exit(1)
    
    # Start WebSocket server
    server = await websockets.serve(
        handler.handle_client,
        "0.0.0.0",  # Bind to all interfaces for WSL2 accessibility from Windows
        8002,
        ping_interval=30,  # Send ping every 30s
        ping_timeout=60    # Wait 60s for pong response (allows for processing time)
    )
    
    logger.info("✅ WebSocket service started successfully with full pipeline")
    logger.info("🔌 Discord bots can connect to: ws://192.168.50.60:8002")
    logger.info("📋 Pipeline includes: STT (Faster-Whisper) → LLM (SmolLM2) → TTS (Kokoro)")
    
    # Keep the service running
    await server.wait_closed()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('websocket_service.log'),
            logging.StreamHandler()
        ]
    )
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 WebSocket service stopped")
    except Exception as e:
        logger.error(f"❌ WebSocket service error: {e}")
        sys.exit(1)