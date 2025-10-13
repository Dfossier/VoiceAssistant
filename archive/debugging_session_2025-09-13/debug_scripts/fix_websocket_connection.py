#!/usr/bin/env python3
"""
Fix WebSocket connection issues - create a working test server
This will help us understand why Pipecat's _client_handler isn't being invoked
"""

import asyncio
import websockets
import json
import logging
import base64
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("WebSocketFix")

class SimpleWebSocketServer:
    """Simple WebSocket server to test client connections"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8004):
        self.host = host
        self.port = port
        self.server = None
        
    async def handle_client(self, websocket, path):
        """Handle client connections - this is equivalent to Pipecat's _client_handler"""
        client_address = websocket.remote_address
        logger.info(f"🔌 Client connected from {client_address}")
        
        try:
            # Send welcome message
            welcome = {
                "type": "welcome",
                "message": "WebSocket server ready",
                "server": "SimpleWebSocketServer"
            }
            await websocket.send(json.dumps(welcome))
            logger.info(f"📤 Sent welcome message to {client_address}")
            
            message_count = 0
            async for message in websocket:
                message_count += 1
                logger.info(f"📨 Received message #{message_count} from {client_address}")
                
                # Log message details
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        logger.info(f"📨 JSON message type: {data.get('type', 'unknown')}")
                        
                        # Echo back different responses based on message type
                        if data.get("type") == "start":
                            response = {
                                "type": "start_ack",
                                "message": "Start frame acknowledged",
                                "session_id": f"session_{message_count}"
                            }
                        elif data.get("type") == "audio_input":
                            audio_data = data.get("data", "")
                            logger.info(f"📨 Audio data length: {len(audio_data)}")
                            response = {
                                "type": "audio_processed",
                                "message": f"Processed {len(audio_data)} bytes of audio",
                                "transcription": "Test transcription from SimpleWebSocketServer"
                            }
                        elif data.get("type") == "text":
                            text = data.get("text", "")
                            response = {
                                "type": "text_response",
                                "response": f"Echo: {text}",
                                "original": text
                            }
                        else:
                            response = {
                                "type": "echo",
                                "original_type": data.get("type", "unknown"),
                                "message": f"Echoing message #{message_count}"
                            }
                        
                        await websocket.send(json.dumps(response))
                        logger.info(f"📤 Sent response to message #{message_count}")
                        
                    except json.JSONDecodeError:
                        logger.warning(f"📨 Non-JSON string message: {message[:100]}...")
                        error_response = {
                            "type": "error",
                            "message": "Invalid JSON format"
                        }
                        await websocket.send(json.dumps(error_response))
                        
                elif isinstance(message, bytes):
                    logger.info(f"📨 Binary message: {len(message)} bytes")
                    # Echo back a binary acknowledgment
                    ack_message = {
                        "type": "binary_ack",
                        "message": f"Received {len(message)} bytes of binary data"
                    }
                    await websocket.send(json.dumps(ack_message))
                    
                else:
                    logger.warning(f"📨 Unknown message type: {type(message)}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"👋 Client {client_address} disconnected normally after {message_count} messages")
        except Exception as e:
            logger.error(f"❌ Error handling client {client_address}: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            
    async def start(self):
        """Start the WebSocket server"""
        logger.info(f"🚀 Starting simple WebSocket server on {self.host}:{self.port}")
        
        try:
            self.server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port,
                ping_interval=None,  # Disable ping/pong
                ping_timeout=None,
                close_timeout=10
            )
            
            logger.info(f"✅ WebSocket server listening on ws://{self.host}:{self.port}")
            logger.info("🔧 This server will help diagnose Discord bot connection issues")
            logger.info("📋 Expected message types: start, audio_input, text")
            
            # Keep the server running
            await self.server.wait_closed()
            
        except Exception as e:
            logger.error(f"❌ Failed to start WebSocket server: {e}")
            raise
            
    async def stop(self):
        """Stop the WebSocket server"""
        if self.server:
            logger.info("🛑 Stopping WebSocket server...")
            self.server.close()
            await self.server.wait_closed()
            logger.info("✅ WebSocket server stopped")

async def test_our_server():
    """Test our own server to make sure it works"""
    logger.info("🧪 Testing our WebSocket server")
    
    try:
        async with websockets.connect("ws://localhost:8004") as websocket:
            logger.info("✅ Connected to our test server")
            
            # Test start message
            start_msg = {"type": "start", "audio_in_sample_rate": 16000}
            await websocket.send(json.dumps(start_msg))
            
            response = await websocket.recv()
            logger.info(f"📥 Response: {response}")
            
            # Test audio message
            test_audio = base64.b64encode(b'\x00\x01' * 512).decode('utf-8')
            audio_msg = {"type": "audio_input", "data": test_audio}
            await websocket.send(json.dumps(audio_msg))
            
            response = await websocket.recv()
            logger.info(f"📥 Audio response: {response}")
            
            logger.info("✅ Our server test passed!")
            
    except Exception as e:
        logger.error(f"❌ Our server test failed: {e}")

async def main():
    """Main function"""
    server = SimpleWebSocketServer()
    
    try:
        # Start server in background
        server_task = asyncio.create_task(server.start())
        
        # Give server time to start
        await asyncio.sleep(1)
        
        # Test our server
        await test_our_server()
        
        # Keep server running for Discord bot testing
        logger.info("🔄 Server ready for Discord bot connections")
        logger.info("💡 Update Discord bot to connect to ws://172.20.104.13:8004")
        logger.info("⌨️  Press Ctrl+C to stop the server")
        
        await server_task
        
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown requested")
        await server.stop()
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        await server.stop()

if __name__ == "__main__":
    asyncio.run(main())