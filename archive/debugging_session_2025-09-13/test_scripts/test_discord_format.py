#!/usr/bin/env python3
"""
Test the exact format that the Discord bot sends to Pipecat
This will simulate the Discord bot's JSON messages and test the full pipeline
"""
import asyncio
import json
import base64
import websockets
import logging
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DiscordFormatTest")

def generate_realistic_audio():
    """Generate more realistic audio that might trigger VAD"""
    # Create 1 second of synthetic speech-like audio (16kHz, mono)
    sample_rate = 16000
    duration = 1.0  # 1 second
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Create a speech-like signal with multiple frequencies and amplitude modulation
    # Simulate formants around 500Hz, 1500Hz, and 2500Hz (typical for speech)
    f1, f2, f3 = 500, 1500, 2500
    amplitude = 0.3
    
    # Create formant-like signal
    signal = (
        np.sin(2 * np.pi * f1 * t) * np.exp(-t * 2) +
        0.5 * np.sin(2 * np.pi * f2 * t) * np.exp(-t * 1.5) +
        0.3 * np.sin(2 * np.pi * f3 * t) * np.exp(-t * 1)
    )
    
    # Add some envelope and noise to make it more speech-like
    envelope = np.exp(-t * 0.5) * np.sin(2 * np.pi * 3 * t) ** 2
    noise = np.random.normal(0, 0.02, len(t))
    signal = signal * envelope + noise
    
    # Normalize and convert to 16-bit PCM
    signal = np.clip(signal * amplitude, -1.0, 1.0)
    audio_data = (signal * 32767).astype(np.int16).tobytes()
    
    logger.info(f"Generated {len(audio_data)} bytes of synthetic speech-like audio")
    return audio_data

async def test_discord_format():
    """Test the exact Discord bot format"""
    uri = "ws://172.20.104.13:8001"
    
    try:
        logger.info(f"🔌 Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Connected successfully!")
            
            # Generate realistic audio
            audio_data = generate_realistic_audio()
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            
            # Test 1: Exact Discord bot format
            discord_message = {
                "type": "audio_input",
                "data": audio_b64,
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm16"
            }
            
            logger.info("🎤 Sending Discord-style audio message...")
            logger.info(f"   - Message size: {len(json.dumps(discord_message))} characters")
            logger.info(f"   - Audio data: {len(audio_data)} bytes")
            logger.info(f"   - Sample rate: 16kHz, mono PCM")
            
            try:
                await websocket.send(json.dumps(discord_message))
                logger.info("✅ Discord format sent successfully")
                
                # Wait for response with longer timeout for AI processing
                logger.info("⏳ Waiting for AI pipeline response (up to 30 seconds)...")
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    if isinstance(response, str):
                        try:
                            resp_data = json.loads(response)
                            logger.info(f"📨 JSON Response: {json.dumps(resp_data, indent=2)}")
                        except json.JSONDecodeError:
                            logger.info(f"📨 Text Response: {response[:200]}...")
                    else:
                        logger.info(f"📨 Binary Response: {len(response)} bytes")
                        
                except asyncio.TimeoutError:
                    logger.warning("⏰ No response within 30 seconds")
                    
            except Exception as e:
                logger.error(f"❌ Send failed: {e}")
                
            # Test 2: Send a simple text message to test LLM processing
            logger.info("📝 Testing text message processing...")
            text_message = {
                "type": "text",
                "text": "Hello, can you hear me?"
            }
            
            try:
                await websocket.send(json.dumps(text_message))
                logger.info("✅ Text message sent successfully")
                
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                    if isinstance(response, str):
                        try:
                            resp_data = json.loads(response)
                            logger.info(f"📨 Text Response: {json.dumps(resp_data, indent=2)}")
                        except json.JSONDecodeError:
                            logger.info(f"📨 Raw Text Response: {response[:200]}...")
                    else:
                        logger.info(f"📨 Binary Response: {len(response)} bytes")
                        
                except asyncio.TimeoutError:
                    logger.warning("⏰ No text response within 15 seconds")
                    
            except Exception as e:
                logger.error(f"❌ Text send failed: {e}")
            
            logger.info("🔚 Test completed - keeping connection open for 5 more seconds...")
            await asyncio.sleep(5)
                
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_discord_format())