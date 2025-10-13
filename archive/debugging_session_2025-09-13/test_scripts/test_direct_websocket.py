#!/usr/bin/env python3
"""
Direct WebSocket server test to see what's happening
"""

import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

connected_clients = set()

async def handle_client(websocket, path):
    """Handle WebSocket client connections"""
    client_addr = websocket.remote_address
    logger.info(f"🔌 Client connected from {client_addr}")
    connected_clients.add(websocket)
    
    try:
        async for message in websocket:
            logger.info(f"📨 Received message from {client_addr}")
            logger.info(f"📨 Message type: {type(message)}")
            logger.info(f"📨 Message length: {len(message) if hasattr(message, '__len__') else 'N/A'}")
            
            # Log message content
            if isinstance(message, bytes):
                logger.info(f"📨 Binary message: {message[:50]}...")
            elif isinstance(message, str):
                logger.info(f"📨 Text message: {message[:200]}...")
                
                # Try to parse as JSON
                try:
                    data = json.loads(message)
                    logger.info(f"📨 JSON parsed: {data}")
                except:
                    pass
                    
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"👋 Client {client_addr} disconnected")
    except Exception as e:
        logger.error(f"❌ Error handling client {client_addr}: {e}")
    finally:
        connected_clients.remove(websocket)

async def main():
    logger.info("🚀 Starting direct WebSocket server on ws://0.0.0.0:8003")
    async with websockets.serve(handle_client, "0.0.0.0", 8003):
        logger.info("✅ Server ready on port 8003")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())