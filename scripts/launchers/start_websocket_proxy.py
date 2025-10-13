#!/usr/bin/env python3
"""
Start the WebSocket proxy from WSL2
This runs a proxy on WSL2 that forwards localhost:8003 to localhost:8002
This avoids the Windows firewall issues with accessing WSL2 IPs
"""

import asyncio
import websockets
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

async def forward_messages(source_ws, target_ws, direction):
    """Forward messages between WebSockets"""
    try:
        async for message in source_ws:
            await target_ws.send(message)
            logger.debug(f"{direction}: Forwarded message")
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"{direction}: Connection closed")
    except Exception as e:
        logger.error(f"{direction}: Error: {e}")

async def handle_client(client_ws, path):
    """Handle incoming client connection"""
    client_addr = client_ws.remote_address
    logger.info(f"New connection from {client_addr}")
    
    try:
        # Connect to local backend
        async with websockets.connect("ws://localhost:8002") as target_ws:
            logger.info(f"Connected to backend ws://localhost:8002")
            
            # Create tasks for bidirectional forwarding
            client_to_target = asyncio.create_task(
                forward_messages(client_ws, target_ws, "Client→Backend")
            )
            target_to_client = asyncio.create_task(
                forward_messages(target_ws, client_ws, "Backend→Client")
            )
            
            # Wait for either connection to close
            await asyncio.gather(client_to_target, target_to_client)
            
    except Exception as e:
        logger.error(f"Failed to connect to backend: {e}")
        await client_ws.close()
    
    logger.info(f"Client {client_addr} disconnected")

async def main():
    """Start the WebSocket proxy server"""
    logger.info("Starting WebSocket proxy on localhost:8003")
    logger.info("Forwarding to ws://localhost:8002")
    
    async with websockets.serve(handle_client, "localhost", 8003):
        logger.info("Proxy server ready - Discord bot should connect to ws://localhost:8003")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Proxy server stopped")