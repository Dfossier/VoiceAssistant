#!/usr/bin/env python3
"""
Test the main backend with manual format
"""

import asyncio
import struct
import json
import websockets
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

class FrameType:
    START_FRAME = "pipecat.frames.frames.StartFrame"
    INPUT_AUDIO_RAW_FRAME = "pipecat.frames.frames.InputAudioRawFrame"

def pack_frame_data(frame_type: str, data: dict) -> bytes:
    """Pack frame data into a binary format"""
    try:
        frame_type_bytes = frame_type.encode('utf-8')
        data_json = json.dumps(data).encode('utf-8')
        
        # Pack the message
        message = struct.pack('!I', len(frame_type_bytes)) + frame_type_bytes
        message += struct.pack('!I', len(data_json)) + data_json
        
        return message
        
    except Exception as e:
        logger.error(f"❌ Failed to pack frame data: {e}")
        return b''

async def test_main_backend():
    """Test the main backend with manual format"""
    uri = "ws://172.20.104.13:8001"
    
    try:
        logger.info(f"🔌 Connecting to main backend: {uri}")
        
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Connected to main backend with hybrid serializer")
            
            # Send StartFrame
            start_data = {
                'frame_type': FrameType.START_FRAME,
                'audio_in_sample_rate': 16000,
                'audio_out_sample_rate': 16000,
                'audio_in_enabled': True,
                'audio_out_enabled': True,
                'allow_interruptions': True
            }
            
            start_message = pack_frame_data(FrameType.START_FRAME, start_data)
            await websocket.send(start_message)
            logger.info("📤 Sent StartFrame to main backend")
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Send some test audio data
            test_audio = bytes([0] * 1600)  # 100ms of silence at 16kHz
            
            audio_data = {
                'frame_type': FrameType.INPUT_AUDIO_RAW_FRAME,
                'audio': list(test_audio),
                'sample_rate': 16000,
                'num_channels': 1
            }
            
            audio_message = pack_frame_data(FrameType.INPUT_AUDIO_RAW_FRAME, audio_data)
            await websocket.send(audio_message)
            logger.info(f"📤 Sent audio frame to main backend: {len(test_audio)} bytes")
            
            # Listen for responses
            logger.info("👂 Listening for responses from main backend...")
            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10)
                    try:
                        if isinstance(response, str):
                            response_data = json.loads(response)
                            logger.info(f"📥 Received JSON response: {response_data}")
                        else:
                            logger.info(f"📥 Received binary response: {len(response)} bytes")
                    except:
                        logger.info(f"📥 Received raw response: {len(response)} bytes")
                    
            except asyncio.TimeoutError:
                logger.info("⏱️ No more responses received from main backend")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_main_backend())