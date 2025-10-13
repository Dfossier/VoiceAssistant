#!/usr/bin/env python3
"""
Simple WebSocket server to test audio streaming from Discord bot
"""

import asyncio
import websockets
import json
import base64
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleAudioReceiver:
    def __init__(self, host="0.0.0.0", port=8001):
        self.host = host
        self.port = port
        self.audio_count = 0
        
    async def handle_client(self, websocket):
        logger.info(f"New client connected from {websocket.remote_address}")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    if data.get("type") == "audio_input":
                        audio_b64 = data.get("data", "")
                        sample_rate = data.get("sample_rate", "unknown")
                        
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            self.audio_count += 1
                            
                            logger.info(f"📡 Received audio chunk #{self.audio_count}: {len(audio_bytes)} bytes @ {sample_rate}Hz")
                            
                            # Simple response back to confirm receipt
                            response = {
                                "type": "audio_received", 
                                "chunk_id": self.audio_count,
                                "size": len(audio_bytes)
                            }
                            await websocket.send(json.dumps(response))
                            
                except json.JSONDecodeError:
                    logger.error("Invalid JSON received")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {websocket.remote_address} disconnected")
        except Exception as e:
            logger.error(f"Error handling client: {e}")
            
    async def start(self):
        logger.info(f"🎧 Starting simple audio receiver on ws://{self.host}:{self.port}")
        
        server = await websockets.serve(self.handle_client, self.host, self.port)
        logger.info("✅ Audio receiver ready - waiting for Discord bot connection...")
        
        await server.wait_closed()

if __name__ == "__main__":
    receiver = SimpleAudioReceiver()
    asyncio.run(receiver.start())