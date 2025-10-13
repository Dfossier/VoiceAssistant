#!/usr/bin/env python
"""
Simple WebSocket client to test Pipecat server
"""

import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_client():
    """Connect to WebSocket server and test communication"""
    
    uri = "ws://127.0.0.1:8765"
    logger.info(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Connected to server!")
            
            # Send a test message
            test_message = json.dumps({
                "type": "text",
                "text": "Hello from test client!"
            })
            
            logger.info(f"Sending: {test_message}")
            await websocket.send(test_message)
            
            # Listen for responses
            logger.info("Listening for responses...")
            
            try:
                while True:
                    response = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=10.0
                    )
                    logger.info(f"Received: {response}")
                    
                    # Try to parse as JSON
                    try:
                        data = json.loads(response)
                        logger.info(f"Parsed data: {data}")
                    except json.JSONDecodeError:
                        logger.info(f"Raw response: {response}")
                        
            except asyncio.TimeoutError:
                logger.info("No more messages (timeout)")
            except websockets.exceptions.ConnectionClosed:
                logger.info("Connection closed by server")
                
    except Exception as e:
        logger.error(f"Connection error: {e}")


async def interactive_client():
    """Interactive WebSocket client"""
    
    uri = "ws://127.0.0.1:8765"
    
    async with websockets.connect(uri) as websocket:
        logger.info("✅ Connected! Type messages to send (or 'quit' to exit)")
        
        # Start listener task
        async def listen():
            try:
                while True:
                    response = await websocket.recv()
                    print(f"\n📥 Received: {response}")
                    print("💬 Enter message: ", end="", flush=True)
            except websockets.exceptions.ConnectionClosed:
                print("\n❌ Connection closed")
        
        listener = asyncio.create_task(listen())
        
        # Send messages
        try:
            while True:
                message = await asyncio.get_event_loop().run_in_executor(
                    None, input, "💬 Enter message: "
                )
                
                if message.lower() == 'quit':
                    break
                    
                # Send as JSON
                data = json.dumps({
                    "type": "text",
                    "text": message
                })
                
                await websocket.send(data)
                print(f"📤 Sent: {data}")
                
        except KeyboardInterrupt:
            pass
        finally:
            listener.cancel()


def main():
    """Main entry point"""
    
    print("\n" + "="*50)
    print("WebSocket Test Client")
    print("="*50 + "\n")
    
    print("1. Run simple test")
    print("2. Interactive mode")
    print("3. Exit")
    
    choice = input("\nSelect option (1-3): ")
    
    if choice == "1":
        asyncio.run(test_client())
    elif choice == "2":
        try:
            asyncio.run(interactive_client())
        except KeyboardInterrupt:
            print("\n\nClient stopped.")
    elif choice == "3":
        print("Goodbye!")
    else:
        print("Invalid option")


if __name__ == "__main__":
    main()