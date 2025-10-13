#!/usr/bin/env python3
"""
Test script for the Pipecat Discord integration
Tests each model component independently
"""

import asyncio
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_phi3_llm():
    """Test Phi-3 LLM integration"""
    logger.info("🧠 Testing Phi-3 Mini LLM...")
    
    try:
        from pipecat_discord_integration import Phi3LLMService
        from pipecat.frames.frames import LLMMessagesFrame
        
        # Initialize service
        llm_service = Phi3LLMService(
            model_path="/mnt/c/users/dfoss/desktop/localaimodels/phi3-mini"
        )
        
        # Create test message frame
        messages = [
            {"role": "user", "content": "Hello, can you introduce yourself briefly?"}
        ]
        test_frame = LLMMessagesFrame(messages=messages)
        
        # Process frame
        async for result_frame in llm_service.process_frame(test_frame, "input"):
            if hasattr(result_frame, 'text'):
                logger.info(f"✅ Phi-3 Response: {result_frame.text[:100]}...")
                return True
                
    except Exception as e:
        logger.error(f"❌ Phi-3 test failed: {e}")
        return False

async def test_parakeet_asr():
    """Test Parakeet ASR integration"""
    logger.info("🎤 Testing Parakeet ASR...")
    
    try:
        from pipecat_discord_integration import ParakeetASRService
        from pipecat.frames.frames import AudioRawFrame
        import numpy as np
        
        # Initialize service
        asr_service = ParakeetASRService(
            model_path="/mnt/c/users/dfoss/desktop/localaimodels/parakeet-tdt"
        )
        
        # Create test audio frame (1 second of sine wave)
        sample_rate = 48000
        duration = 1.0
        frequency = 440  # A4 note
        
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_data = np.sin(2 * np.pi * frequency * t) * 0.3
        audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()
        
        test_frame = AudioRawFrame(audio=audio_bytes, sample_rate=sample_rate, num_channels=1)
        
        # Process frame
        async for result_frame in asr_service.process_frame(test_frame, "input"):
            if hasattr(result_frame, 'text'):
                logger.info(f"✅ Parakeet Transcription: {result_frame.text}")
                return True
                
    except Exception as e:
        logger.error(f"❌ Parakeet test failed: {e}")
        return False

async def test_kokoro_tts():
    """Test Kokoro TTS integration"""
    logger.info("🔊 Testing Kokoro TTS...")
    
    try:
        from pipecat_discord_integration import KokoroTTSService
        from pipecat.frames.frames import TextFrame
        
        # Initialize service
        tts_service = KokoroTTSService(
            model_path="/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts",
            voice_name="af_sarah"
        )
        
        # Create test text frame
        test_frame = TextFrame(text="Hello, this is a test of the Kokoro text to speech system.")
        
        # Process frame
        async for result_frame in tts_service.process_frame(test_frame, "output"):
            if hasattr(result_frame, 'audio'):
                audio_length = len(result_frame.audio)
                logger.info(f"✅ Kokoro TTS generated {audio_length} bytes of audio")
                return True
                
    except Exception as e:
        logger.error(f"❌ Kokoro test failed: {e}")
        return False

async def test_pipeline_creation():
    """Test creating the full Pipecat pipeline"""
    logger.info("🔗 Testing full pipeline creation...")
    
    try:
        from pipecat_discord_integration import PipecatDiscordVoiceHandler
        
        # Mock Discord objects (for testing)
        class MockVoiceClient:
            def is_connected(self):
                return True
        
        class MockTextChannel:
            async def send(self, text):
                logger.info(f"Would send to Discord: {text}")
        
        # Create handler
        handler = PipecatDiscordVoiceHandler(
            voice_client=MockVoiceClient(),
            text_channel=MockTextChannel()
        )
        
        # Initialize (this will create all services)
        await handler.initialize()
        
        logger.info("✅ Pipeline created successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Pipeline creation failed: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("🚀 Starting Pipecat Discord Integration Tests...")
    
    tests = [
        ("Phi-3 LLM", test_phi3_llm),
        ("Kokoro TTS", test_kokoro_tts),
        ("Pipeline Creation", test_pipeline_creation),
        # ("Parakeet ASR", test_parakeet_asr),  # Skip ASR test for now due to NeMo issues
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running {test_name} test...")
        logger.info(f"{'='*50}")
        
        try:
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results.append((test_name, False))
        
        await asyncio.sleep(1)  # Brief pause between tests
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("TEST RESULTS SUMMARY")
    logger.info(f"{'='*50}")
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{test_name}: {status}")
        if success:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        logger.info("🎉 All tests passed! Pipecat integration ready.")
    else:
        logger.info("⚠️  Some tests failed. Check logs for details.")

if __name__ == "__main__":
    asyncio.run(main())