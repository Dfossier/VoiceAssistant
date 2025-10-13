#!/usr/bin/env python3
"""
Direct test of the running Pipecat WebSocket server
Tests the actual server running on port 8001 to understand why connections fail
"""

import asyncio
import websockets
import json
import base64
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("PipecatTest")

async def test_pipecat_server():
    """Test the actual Pipecat server running on port 8001"""
    uri = "ws://172.20.104.13:8001"
    
    logger.info(f"Testing direct connection to Pipecat server at {uri}")
    
    try:
        # Try to connect with various WebSocket settings
        logger.info("Attempting WebSocket connection...")
        
        async with websockets.connect(
            uri,
            timeout=10,
            close_timeout=5,
            ping_timeout=20,
            ping_interval=None  # Disable pings for testing
        ) as websocket:
            logger.info("✅ Successfully connected to Pipecat server!")
            logger.info(f"WebSocket state: {websocket.state}")
            logger.info(f"Remote address: {websocket.remote_address}")
            
            # Test 1: Send a StartFrame equivalent (Pipecat expects this)
            logger.info("📤 Sending StartFrame...")
            start_frame = {
                "type": "start",
                "params": {
                    "audio_in_sample_rate": 16000,
                    "audio_out_sample_rate": 16000,
                    "allow_interruptions": True
                }
            }
            
            await websocket.send(json.dumps(start_frame))
            logger.info("✅ StartFrame sent successfully")
            
            # Wait for acknowledgment
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"📥 Received response: {response}")
            except asyncio.TimeoutError:
                logger.warning("⏰ No response to StartFrame (may be normal)")
            
            # Test 2: Send a text message
            logger.info("📤 Sending text message...")
            text_message = {
                "type": "text",
                "text": "Hello Pipecat!"
            }
            
            await websocket.send(json.dumps(text_message))
            logger.info("✅ Text message sent successfully")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                logger.info(f"📥 Received text response: {response}")
            except asyncio.TimeoutError:
                logger.warning("⏰ No response to text message")
            
            # Test 3: Send audio data (like Discord bot does)
            logger.info("📤 Sending audio frame...")
            
            # Create test PCM audio data (silence)
            test_audio = b'\x00\x01' * 1024  # 2048 bytes of test PCM data
            audio_message = {
                "type": "audio_input",
                "data": base64.b64encode(test_audio).decode('utf-8'),
                "sample_rate": 16000,
                "channels": 1,
                "format": "pcm16"
            }
            
            await websocket.send(json.dumps(audio_message))
            logger.info("✅ Audio frame sent successfully")
            
            # Wait for audio processing response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                logger.info(f"📥 Received audio response: {response[:200]}...")
            except asyncio.TimeoutError:
                logger.warning("⏰ No response to audio frame")
            
            # Test 4: Try binary data (protobuf mode)
            logger.info("📤 Sending binary audio...")
            await websocket.send(test_audio)
            logger.info("✅ Binary audio sent successfully")
            
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                logger.info(f"📥 Received binary response: {type(response)} ({len(response) if hasattr(response, '__len__') else 'N/A'} bytes)")
            except asyncio.TimeoutError:
                logger.warning("⏰ No response to binary audio")
            
            # Keep connection alive for a bit to see if server sends anything
            logger.info("🔄 Keeping connection alive for 10 seconds...")
            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    logger.info(f"📥 Unexpected message: {response}")
            except asyncio.TimeoutError:
                logger.info("ℹ️ No more messages from server")
            
            logger.info("✅ Test completed successfully")
            
    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"❌ Connection closed: {e.code} - {e.reason}")
    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"❌ Invalid status code: {e.status_code}")
    except websockets.exceptions.InvalidURI as e:
        logger.error(f"❌ Invalid URI: {e}")
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")

async def test_simple_connection():
    """Test the simplest possible connection"""
    ports_to_test = [8001, 8002]
    
    for port in ports_to_test:
        uri = f"ws://172.20.104.13:{port}"
        logger.info(f"Testing simple connection to {uri}")
        
        try:
            # Just try to connect and immediately close
            websocket = await websockets.connect(uri, timeout=5)
            logger.info(f"✅ Simple connection successful to port {port}!")
            logger.info(f"WebSocket state: {websocket.state}")
            await websocket.close()
            logger.info(f"✅ Simple connection closed cleanly on port {port}")
            return True, port
        except Exception as e:
            logger.error(f"❌ Simple connection failed on port {port}: {e}")
    
    return False, None

async def main():
    """Run all Pipecat server tests"""
    logger.info("🧪 Testing WebSocket servers on ports 8001 and 8002")
    logger.info("=" * 60)
    
    # Test 1: Simple connection
    logger.info("\n🔍 Test 1: Simple Connection")
    logger.info("-" * 30)
    simple_success, working_port = await test_simple_connection()
    
    if simple_success:
        logger.info(f"✅ Found working WebSocket server on port {working_port}")
        # Test 2: Full protocol test
        logger.info("\n🔍 Test 2: Full Protocol Test")
        logger.info("-" * 30)
        await test_pipecat_server()
    else:
        logger.error("❌ Skipping full test - no working WebSocket server found")
    
    logger.info("\n" + "=" * 60)
    logger.info("🧪 WebSocket server tests completed")

if __name__ == "__main__":
    asyncio.run(main())