#!/usr/bin/env python3
"""
Diagnostic tool to trace WebSocket connection issues between Discord bot and Pipecat
Tests different connection scenarios to identify why _client_handler isn't being invoked
"""

import asyncio
import websockets
import json
import logging
import time
from pathlib import Path

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("WebSocketDebug")

class WebSocketConnectionTester:
    """Test WebSocket connections to diagnose Pipecat handler issues"""
    
    def __init__(self):
        self.wsl_ip = "172.20.104.13"
        self.port = 8001
        
    async def test_basic_connection(self):
        """Test basic WebSocket connection"""
        uri = f"ws://{self.wsl_ip}:{self.port}"
        logger.info(f"Testing basic connection to {uri}")
        
        try:
            async with websockets.connect(uri) as websocket:
                logger.info("✅ Basic WebSocket connection successful")
                
                # Send a simple ping
                ping_msg = {"type": "ping", "timestamp": time.time()}
                await websocket.send(json.dumps(ping_msg))
                logger.info(f"📤 Sent ping: {ping_msg}")
                
                # Wait for response or timeout
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    logger.info(f"📥 Received response: {response}")
                except asyncio.TimeoutError:
                    logger.warning("⏰ No response received within 5 seconds")
                    
        except Exception as e:
            logger.error(f"❌ Basic connection failed: {e}")
            return False
            
        return True
    
    async def test_pipecat_protocol(self):
        """Test Pipecat-specific protocol messages"""
        uri = f"ws://{self.wsl_ip}:{self.port}"
        logger.info(f"Testing Pipecat protocol to {uri}")
        
        try:
            async with websockets.connect(uri) as websocket:
                logger.info("✅ Connected for Pipecat protocol test")
                
                # Send Pipecat StartFrame equivalent
                start_frame = {
                    "type": "start",
                    "audio_in_sample_rate": 16000,
                    "audio_out_sample_rate": 16000,
                    "allow_interruptions": True,
                    "enable_metrics": True,
                    "enable_usage_metrics": True
                }
                
                await websocket.send(json.dumps(start_frame))
                logger.info(f"📤 Sent StartFrame: {start_frame}")
                
                # Wait for acknowledgment
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    logger.info(f"📥 Received acknowledgment: {response}")
                except asyncio.TimeoutError:
                    logger.warning("⏰ No StartFrame acknowledgment received")
                
                # Send test audio data
                import base64
                test_audio = b'\x00' * 1024  # Silent audio
                audio_frame = {
                    "type": "audio_input",
                    "data": base64.b64encode(test_audio).decode('utf-8'),
                    "sample_rate": 16000,
                    "channels": 1,
                    "format": "pcm16"
                }
                
                await websocket.send(json.dumps(audio_frame))
                logger.info(f"📤 Sent audio frame: {len(test_audio)} bytes")
                
                # Wait for processing
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                    logger.info(f"📥 Received audio response: {response[:100]}...")
                except asyncio.TimeoutError:
                    logger.warning("⏰ No audio processing response received")
                    
        except Exception as e:
            logger.error(f"❌ Pipecat protocol test failed: {e}")
            return False
            
        return True
    
    async def test_localhost_vs_wsl_ip(self):
        """Test localhost vs WSL IP connection"""
        test_uris = [
            f"ws://localhost:{self.port}",
            f"ws://127.0.0.1:{self.port}",
            f"ws://{self.wsl_ip}:{self.port}",
            f"ws://0.0.0.0:{self.port}"
        ]
        
        for uri in test_uris:
            logger.info(f"Testing connection to {uri}")
            try:
                async with websockets.connect(uri, timeout=3.0) as websocket:
                    logger.info(f"✅ {uri} - Connection successful")
                    await websocket.ping()
                    logger.info(f"✅ {uri} - Ping successful")
            except Exception as e:
                logger.error(f"❌ {uri} - Failed: {e}")
    
    async def test_server_response_times(self):
        """Test server response characteristics"""
        uri = f"ws://{self.wsl_ip}:{self.port}"
        logger.info(f"Testing server response times to {uri}")
        
        try:
            start_time = time.time()
            async with websockets.connect(uri) as websocket:
                connect_time = time.time() - start_time
                logger.info(f"⏱️ Connection time: {connect_time:.3f}s")
                
                # Test multiple message exchanges
                for i in range(3):
                    msg_start = time.time()
                    test_msg = {"type": "test", "sequence": i, "timestamp": msg_start}
                    await websocket.send(json.dumps(test_msg))
                    
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        msg_time = time.time() - msg_start
                        logger.info(f"⏱️ Message {i} round-trip: {msg_time:.3f}s")
                    except asyncio.TimeoutError:
                        logger.warning(f"⏰ Message {i} timed out")
                        
        except Exception as e:
            logger.error(f"❌ Response time test failed: {e}")
    
    async def simulate_discord_bot_behavior(self):
        """Simulate exact Discord bot connection behavior"""
        uri = f"ws://{self.wsl_ip}:{self.port}"
        logger.info(f"Simulating Discord bot behavior to {uri}")
        
        try:
            # This simulates the exact connection process from direct_audio_bot.py
            websocket = await websockets.connect(uri)
            logger.info("✅ Simulated Discord bot connection established")
            
            # Send StartFrame exactly as the bot does
            start_message = {
                "type": "start",
                "audio_in_sample_rate": 16000,
                "audio_out_sample_rate": 16000,
                "allow_interruptions": True,
                "enable_metrics": True,
                "enable_usage_metrics": True
            }
            
            await websocket.send(json.dumps(start_message))
            logger.info("📤 Sent StartFrame exactly as Discord bot does")
            
            # Wait for any immediate response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                logger.info(f"📥 Immediate response: {response}")
            except asyncio.TimeoutError:
                logger.info("ℹ️ No immediate response (this might be normal)")
            
            # Simulate periodic audio data like the bot
            import base64
            for chunk_num in range(3):
                # Create test audio chunk
                test_audio = b'\x00\x01' * 512  # 1024 bytes of test data
                
                message = {
                    "type": "audio_input",
                    "data": base64.b64encode(test_audio).decode('utf-8'),
                    "sample_rate": 16000,
                    "channels": 1,
                    "format": "pcm16"
                }
                
                await websocket.send(json.dumps(message))
                logger.info(f"📤 Sent audio chunk #{chunk_num+1} like Discord bot")
                
                # Wait for processing
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    logger.info(f"📥 Audio response {chunk_num+1}: {response[:50]}...")
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ No response to audio chunk {chunk_num+1}")
                
                await asyncio.sleep(0.5)  # Simulate audio timing
            
            await websocket.close()
            logger.info("✅ Simulated Discord bot session complete")
            
        except Exception as e:
            logger.error(f"❌ Discord bot simulation failed: {e}")
    
    async def run_all_tests(self):
        """Run comprehensive WebSocket diagnostics"""
        logger.info("🧪 Starting comprehensive WebSocket diagnostics")
        logger.info("="*60)
        
        tests = [
            ("Basic Connection Test", self.test_basic_connection),
            ("Localhost vs WSL IP Test", self.test_localhost_vs_wsl_ip),
            ("Server Response Times", self.test_server_response_times),
            ("Pipecat Protocol Test", self.test_pipecat_protocol),
            ("Discord Bot Simulation", self.simulate_discord_bot_behavior),
        ]
        
        for test_name, test_func in tests:
            logger.info(f"\n🔍 Running: {test_name}")
            logger.info("-" * 40)
            try:
                await test_func()
                logger.info(f"✅ {test_name} completed")
            except Exception as e:
                logger.error(f"❌ {test_name} failed: {e}")
            
            await asyncio.sleep(1)  # Brief pause between tests
        
        logger.info("\n" + "="*60)
        logger.info("🧪 All WebSocket diagnostics completed")

async def main():
    """Main diagnostic function"""
    tester = WebSocketConnectionTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())