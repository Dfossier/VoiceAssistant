#!/usr/bin/env python3
"""
Wait for all services to be ready before starting Discord bot
"""

import asyncio
import websockets
import json
import time
import sys
from pathlib import Path

# Load config
config_path = Path(__file__).parent.parent.parent / "config" / "services.json"
with open(config_path, 'r') as f:
    config = json.load(f)

async def check_websocket_service():
    """Check if WebSocket service is ready"""
    url = config['websocket_service']['url'].replace('ws://', 'http://') + '/health'
    
    # Try simple WebSocket connection instead
    try:
        async with websockets.connect(
            config['websocket_service']['url'],
            open_timeout=5
        ) as ws:
            # Send a ping
            await ws.send(json.dumps({"type": "ping"}))
            # Wait for any response
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            return True
    except Exception as e:
        return False

async def wait_for_services():
    """Wait for all services to be ready"""
    print("🔄 Waiting for services to start...")
    
    timeout = config['websocket_service']['startup_timeout']
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Check WebSocket service
        if await check_websocket_service():
            print("✅ WebSocket service is ready!")
            print(f"✅ All services ready after {time.time() - start_time:.1f}s")
            return True
        
        print(f"⏳ Waiting... ({int(time.time() - start_time)}s/{timeout}s)")
        await asyncio.sleep(config['discord_bot']['connection']['retry_delay'])
    
    print(f"❌ Services failed to start within {timeout}s")
    return False

if __name__ == "__main__":
    if asyncio.run(wait_for_services()):
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Failure