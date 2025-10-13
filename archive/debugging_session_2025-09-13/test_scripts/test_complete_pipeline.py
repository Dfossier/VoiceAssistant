#!/usr/bin/env python3
"""
Complete test of the fixed Pipecat pipeline
Tests both audio and text input/output
"""
import asyncio
import json
import base64
import websockets
import logging
import numpy as np
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CompletePipelineTest")

async def test_complete_pipeline():
    """Test the complete voice pipeline"""
    uri = "ws://172.20.104.13:8001"  # WSL2 IP address
    
    # Test 1: Generate "Hello" audio
    logger.info("🎤 Test 1: Generating 'Hello' audio...")
    # For now, use silence to test the pipeline
    sample_rate = 16000
    duration = 0.5  # 500ms of silence
    audio_data = np.zeros(int(sample_rate * duration), dtype=np.int16)
    audio_bytes = audio_data.tobytes()
    
    try:
        logger.info(f"🔌 Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Connected successfully!")
            
            # Send a text message first to test LLM
            logger.info("\n📝 Test 1: Text input")
            text_msg = {
                "type": "text_input",
                "text": "Hello! Can you hear me? Please respond with a greeting."
            }
            await websocket.send(json.dumps(text_msg))
            logger.info("✅ Sent text input")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                response_data = json.loads(response)
                logger.info(f"📨 Response type: {response_data.get('type')}")
                
                if response_data.get("type") == "text":
                    logger.info(f"💬 AI says: {response_data['text']}")
                elif response_data.get("type") == "audio_output":
                    audio_size = len(base64.b64decode(response_data['data']))
                    logger.info(f"🔊 Received audio: {audio_size} bytes")
                    
            except asyncio.TimeoutError:
                logger.warning("⏰ No response received for text input")
                
            # Test 2: Send audio
            logger.info("\n🎤 Test 2: Audio input")
            audio_msg = {
                "type": "audio_input",
                "data": base64.b64encode(audio_bytes).decode('utf-8'),
                "sample_rate": sample_rate,
                "channels": 1,
                "format": "pcm16"
            }
            await websocket.send(json.dumps(audio_msg))
            logger.info("✅ Sent audio input (silence for VAD test)")
            
            # Listen for any responses
            logger.info("\n👂 Listening for pipeline responses...")
            no_response_count = 0
            while no_response_count < 3:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    response_data = json.loads(response)
                    
                    msg_type = response_data.get("type", "unknown")
                    if msg_type == "text":
                        logger.info(f"📝 Transcription/Response: {response_data['text']}")
                    elif msg_type == "audio_output":
                        audio_size = len(base64.b64decode(response_data['data']))
                        logger.info(f"🔊 Audio response: {audio_size} bytes")
                    else:
                        logger.info(f"📨 Other response: {msg_type}")
                        
                    no_response_count = 0
                    
                except asyncio.TimeoutError:
                    no_response_count += 1
                    if no_response_count < 3:
                        logger.info("⏰ Waiting for more responses...")
                except json.JSONDecodeError as e:
                    logger.warning(f"Received non-JSON response: {e}")
                except Exception as e:
                    logger.error(f"Error receiving: {e}")
                    break
                    
            logger.info("\n✅ Test completed!")
            
    except websockets.exceptions.WebSocketException as e:
        logger.error(f"❌ WebSocket error: {e}")
        logger.info("Make sure the pipeline is running: python run_fixed_pipeline.py")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    # Check if pipeline URL is provided
    if len(sys.argv) > 1:
        uri = sys.argv[1]
        logger.info(f"Using custom URI: {uri}")
    
    asyncio.run(test_complete_pipeline())