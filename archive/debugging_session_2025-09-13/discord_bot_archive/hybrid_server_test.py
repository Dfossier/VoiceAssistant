#!/usr/bin/env python3
"""
Hybrid WebSocket server that can handle both manual format and Pipecat Protobuf
This allows testing with the Windows-compatible manual format
"""

import asyncio
import json
import struct
import logging
from typing import Optional
import websockets

from pipecat.frames.frames import InputAudioRawFrame, OutputAudioRawFrame, StartFrame, TextFrame
from pipecat.serializers.protobuf import ProtobufFrameSerializer

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

class HybridFrameHandler:
    """Handles both manual format and Pipecat Protobuf format"""
    
    def __init__(self):
        self.protobuf_serializer = ProtobufFrameSerializer()
        self.setup_completed = False
        
    async def setup(self):
        """Setup the Protobuf serializer"""
        if not self.setup_completed:
            start_frame = StartFrame(
                audio_in_sample_rate=16000,
                audio_out_sample_rate=16000,
                audio_in_enabled=True,
                audio_out_enabled=True
            )
            await self.protobuf_serializer.setup(start_frame)
            self.setup_completed = True
            logger.info("✅ Protobuf serializer setup completed")
    
    async def parse_message(self, message: bytes):
        """Parse incoming message, trying both formats"""
        try:
            # First, try manual format
            manual_frame = await self.parse_manual_format(message)
            if manual_frame:
                logger.info(f"📥 Parsed manual frame: {manual_frame['frame_type']}")
                return manual_frame
                
        except Exception as e:
            logger.debug(f"Manual format parsing failed: {e}")
        
        try:
            # Then try Pipecat Protobuf format
            await self.setup()
            protobuf_frame = await self.protobuf_serializer.deserialize(message)
            if protobuf_frame:
                logger.info(f"📥 Parsed Protobuf frame: {type(protobuf_frame).__name__}")
                return self.frame_to_dict(protobuf_frame)
                
        except Exception as e:
            logger.debug(f"Protobuf format parsing failed: {e}")
        
        # If neither works, return None
        logger.warning(f"❌ Could not parse message: {len(message)} bytes")
        return None
    
    async def parse_manual_format(self, message: bytes) -> Optional[dict]:
        """Parse manual format: [frame_type_len][frame_type][data_len][data_json]"""
        if len(message) < 8:  # Minimum size for headers
            return None
            
        offset = 0
        
        # Read frame type length
        frame_type_len = struct.unpack('!I', message[offset:offset+4])[0]
        offset += 4
        
        if offset + frame_type_len > len(message):
            return None
            
        # Read frame type
        frame_type = message[offset:offset+frame_type_len].decode('utf-8')
        offset += frame_type_len
        
        if offset + 4 > len(message):
            return None
            
        # Read data length
        data_len = struct.unpack('!I', message[offset:offset+4])[0]
        offset += 4
        
        if offset + data_len != len(message):
            return None
            
        # Read and parse data
        data_json = message[offset:offset+data_len].decode('utf-8')
        data = json.loads(data_json)
        
        return data
    
    def frame_to_dict(self, frame) -> dict:
        """Convert Pipecat frame to dict format"""
        frame_dict = {
            'frame_type': type(frame).__name__,
        }
        
        if isinstance(frame, StartFrame):
            frame_dict.update({
                'audio_in_sample_rate': frame.audio_in_sample_rate,
                'audio_out_sample_rate': frame.audio_out_sample_rate,
                'audio_in_enabled': frame.audio_in_enabled,
                'audio_out_enabled': frame.audio_out_enabled,
            })
        elif isinstance(frame, InputAudioRawFrame):
            frame_dict.update({
                'audio': frame.audio,
                'sample_rate': frame.sample_rate,
                'num_channels': frame.num_channels
            })
        elif isinstance(frame, TextFrame):
            frame_dict.update({
                'text': frame.text
            })
            
        return frame_dict

class HybridWebSocketServer:
    """WebSocket server that handles both formats"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8002):
        self.host = host
        self.port = port
        self.frame_handler = HybridFrameHandler()
        self.clients = set()
        
    async def handle_client(self, websocket, path):
        """Handle individual client connection"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"🔌 New client connected: {client_id}")
        self.clients.add(websocket)
        
        try:
            async for message in websocket:
                logger.info(f"📨 Received message from {client_id}: {len(message)} bytes")
                
                # Parse the message
                parsed_frame = await self.frame_handler.parse_message(message)
                
                if parsed_frame:
                    await self.process_frame(websocket, parsed_frame)
                else:
                    logger.warning(f"⚠️ Could not process message from {client_id}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"📡 Client {client_id} disconnected normally")
        except Exception as e:
            logger.error(f"❌ Error handling client {client_id}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.clients.discard(websocket)
            logger.info(f"🔌 Client {client_id} connection closed")
    
    async def process_frame(self, websocket, frame_data: dict):
        """Process parsed frame data"""
        frame_type = frame_data.get('frame_type', 'Unknown')
        
        if 'StartFrame' in frame_type:
            logger.info("🚀 Received StartFrame - pipeline ready")
            # Send acknowledgment back
            response = {"type": "start_ack", "message": "Pipeline started"}
            await websocket.send(json.dumps(response).encode())
            
        elif 'InputAudioRawFrame' in frame_type:
            audio_data = frame_data.get('audio', [])
            if isinstance(audio_data, list):
                audio_bytes = bytes(audio_data)
            else:
                audio_bytes = audio_data
                
            logger.info(f"🎤 Received audio: {len(audio_bytes)} bytes, sample_rate: {frame_data.get('sample_rate', 'unknown')}")
            
            # Simulate STT processing
            if len(audio_bytes) > 0:
                # Send back a simulated text response every few chunks
                import time
                current_time = int(time.time())
                if current_time % 5 == 0:  # Every 5 seconds
                    response_text = f"I hear audio at {current_time}. This is a test response from the hybrid server."
                    response = {
                        "type": "text_response",
                        "text": response_text,
                        "timestamp": current_time
                    }
                    await websocket.send(json.dumps(response).encode())
                    logger.info(f"📤 Sent test response: {response_text}")
        
        elif 'TextFrame' in frame_type:
            text = frame_data.get('text', '')
            logger.info(f"💬 Received text: '{text}'")
            
            # Echo the text back
            response = {
                "type": "text_echo", 
                "original": text,
                "echo": f"Echo: {text}"
            }
            await websocket.send(json.dumps(response).encode())
    
    async def start_server(self):
        """Start the WebSocket server"""
        logger.info(f"🚀 Starting hybrid WebSocket server on {self.host}:{self.port}")
        
        server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            ping_interval=30,
            ping_timeout=10
        )
        
        logger.info(f"✅ Hybrid server listening on ws://{self.host}:{self.port}")
        logger.info("🔄 Server supports both manual format and Pipecat Protobuf format")
        
        # Keep the server running
        await server.wait_closed()

async def main():
    """Main function to run the hybrid server"""
    server = HybridWebSocketServer()
    
    try:
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("⏹️ Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())