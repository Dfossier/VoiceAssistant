#!/usr/bin/env python3
"""Simple test of port 8001 connectivity"""

import asyncio
import websockets
import json
import base64
import logging
import numpy as np
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_speech_like_audio(duration=2, sample_rate=16000):
    """Generate audio that looks like speech"""
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples, False)
    
    # Create a complex waveform that looks like speech
    # Mix multiple frequencies to simulate speech patterns
    audio = np.sin(2 * np.pi * 200 * t) * 0.3  # Base frequency
    audio += np.sin(2 * np.pi * 400 * t) * 0.2  # Harmonic
    audio += np.sin(2 * np.pi * 800 * t) * 0.1  # Higher harmonic
    
    # Add some amplitude variation to simulate speech
    envelope = np.sin(2 * np.pi * 3 * t) * 0.3 + 0.7
    audio = audio * envelope
    
    # Convert to int16 PCM
    audio_int16 = (audio * 16000).astype(np.int16)
    return audio_int16.tobytes()

async def test_port8001():
    """Test port 8001 with synthetic speech audio"""
    
    uri = "ws://localhost:8001"
    logger.info(f"Testing port 8001 at {uri}...")
    
    try:
        async with websockets.connect(uri, timeout=10) as websocket:
            logger.info("✅ Connected to port 8001!")
            
            # Send start message
            start_msg = {
                "type": "start",
                "timestamp": datetime.now(timezone.utc).timestamp()
            }
            await websocket.send(json.dumps(start_msg))
            logger.info("📤 Sent start message")
            
            # Generate synthetic speech audio
            audio_bytes = generate_speech_like_audio(duration=2)
            
            # Send audio in chunks like Discord bot does
            chunk_size = 1600  # 100ms chunks at 16kHz
            total_chunks = len(audio_bytes) // chunk_size
            
            logger.info(f"📤 Sending {total_chunks} chunks of synthetic speech audio...")
            
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i+chunk_size]
                if len(chunk) < chunk_size:
                    # Pad the last chunk
                    chunk += b'\x00' * (chunk_size - len(chunk))
                
                audio_msg = {
                    "type": "audio_input",
                    "data": base64.b64encode(chunk).decode('utf-8'),
                    "sample_rate": 16000,
                    "channels": 1,
                    "format": "pcm",
                    "timestamp": datetime.now(timezone.utc).timestamp()
                }
                
                await websocket.send(json.dumps(audio_msg))
                
                # Small delay between chunks
                await asyncio.sleep(0.1)
            
            logger.info("📤 Finished sending synthetic speech audio")
            
            # Listen for responses for longer
            logger.info("👂 Listening for pipeline responses...")
            response_count = 0
            
            try:
                while response_count < 10:  # Listen for up to 10 messages
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        data = json.loads(message)
                        msg_type = data.get("type")
                        response_count += 1
                        
                        if msg_type == "transcription":
                            transcription = data.get('text', '')
                            logger.info(f"🗣️ TRANSCRIPTION: '{transcription}'")
                        elif msg_type == "text_output":
                            response = data.get('text', '')
                            logger.info(f"💬 AI RESPONSE: '{response}'")
                        elif msg_type == "audio_output":
                            audio_len = len(data.get('data', ''))
                            logger.info(f"🔊 TTS AUDIO: {audio_len} chars")
                        else:
                            logger.info(f"📨 MESSAGE: {msg_type}")
                        
                    except asyncio.TimeoutError:
                        logger.info(f"⏱️ Timeout waiting for response #{response_count}")
                        break
                        
            except websockets.exceptions.ConnectionClosed:
                logger.info("🔌 Connection closed by server")
            
            if response_count == 0:
                logger.error("❌ No responses received - pipeline not processing")
            else:
                logger.info(f"✅ Received {response_count} responses from pipeline")
            
    except Exception as e:
        logger.error(f"❌ Connection or processing failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    logger.info("🎯 Testing if the Pipecat pipeline on port 8001 is processing audio")
    asyncio.run(test_port8001())