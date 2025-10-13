#!/usr/bin/env python3
"""
Simple WebSocket proxy to forward Windows localhost to WSL2
This bypasses Windows firewall issues with WSL2 networking
"""

import asyncio
import websockets
import logging

# Configuration
LISTEN_HOST = "localhost"  # Only listen on localhost for Windows
LISTEN_PORT = 8003
TARGET_URL = "ws://192.168.50.60:8002"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

async def forward_messages(source_ws, target_ws, direction):
    """Forward messages between WebSockets"""
    try:
        async for message in source_ws:
            if isinstance(message, bytes):
                await target_ws.send(message)
            else:
                await target_ws.send(message)
            logger.debug(f"{direction}: Forwarded message")
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"{direction}: Connection closed")
    except Exception as e:
        logger.error(f"{direction}: Error: {e}")

async def handle_client(client_ws):
    """Handle incoming client connection"""
    try:
        client_addr = client_ws.remote_address
    except:
        client_addr = "unknown"
    logger.info(f"New client connection from {client_addr}")
    
    try:
        # Connect to target WSL2 WebSocket with timeout
        logger.info(f"Attempting to connect to {TARGET_URL}")
        logger.info(f"Connection parameters: open_timeout=30, ping disabled")
        
        start_time = asyncio.get_event_loop().time()
        async with websockets.connect(
            TARGET_URL,
            open_timeout=30,
            close_timeout=10,
            ping_interval=None,
            ping_timeout=None,
            compression=None
        ) as target_ws:
            connection_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"Successfully connected to {TARGET_URL} in {connection_time:.2f}s")
            logger.info(f"Connected to target {TARGET_URL}")
            
            # Create tasks for bidirectional forwarding
            client_to_target = asyncio.create_task(
                forward_messages(client_ws, target_ws, "Client→Target")
            )
            target_to_client = asyncio.create_task(
                forward_messages(target_ws, client_ws, "Target→Client")
            )
            
            # Wait for either connection to close
            await asyncio.gather(client_to_target, target_to_client)
            
    except asyncio.TimeoutError as e:
        logger.error(f"Timeout connecting to target {TARGET_URL}: {e}")
        try:
            await client_ws.close(code=1011, reason="Backend timeout")
        except:
            pass
    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"Target connection closed during handshake: {e}")
        try:
            await client_ws.close(code=1011, reason="Backend closed")
        except:
            pass
    except Exception as e:
        logger.error(f"Failed to connect to target {TARGET_URL}: {type(e).__name__}: {e}")
        try:
            await client_ws.close(code=1011, reason="Backend error")
        except:
            pass
    
    logger.info(f"Client {client_addr} disconnected")

async def main():
    """Start the WebSocket proxy server"""
    logger.info(f"Starting WebSocket proxy on {LISTEN_HOST}:{LISTEN_PORT}")
    logger.info(f"Forwarding to {TARGET_URL}")
    
    server = await websockets.serve(handle_client, LISTEN_HOST, LISTEN_PORT)
    logger.info("Proxy server ready")
    await server.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Proxy server stopped")