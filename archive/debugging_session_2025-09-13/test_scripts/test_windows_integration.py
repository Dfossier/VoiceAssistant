#!/usr/bin/env python3
"""
Test script for Windows Pipecat integration
Tests the Windows-based AI models independently
"""

import asyncio
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_windows_phi3():
    """Test Windows Phi-3 integration"""
    logger.info("🧠 Testing Windows Phi-3...")
    
    try:
        from windows_pipecat_integration import WindowsPhi3Service
        
        # Initialize service
        phi3_service = WindowsPhi3Service(
            model_path="/mnt/c/users/dfoss/desktop/localaimodels/phi3-mini"
        )
        
        # Initialize 
        await phi3_service.initialize()
        
        if phi3_service.is_ready:
            # Test generation
            response = await phi3_service._generate_response("Hello, can you tell me about yourself briefly?")
            logger.info(f"✅ Phi-3 Response: {response[:100]}...")
            return True
        else:
            logger.error("❌ Phi-3 not ready after initialization")
            return False
                
    except Exception as e:
        logger.error(f"❌ Windows Phi-3 test failed: {e}")
        return False

async def test_windows_whisper():
    """Test Windows Whisper integration"""
    logger.info("🎤 Testing Windows Whisper...")
    
    try:
        from windows_pipecat_integration import WindowsWhisperService
        
        # Initialize service
        whisper_service = WindowsWhisperService()
        
        # Initialize
        await whisper_service.initialize()
        
        if whisper_service.is_ready:
            logger.info("✅ Whisper initialized successfully")
            # Note: We won't test actual transcription here as it requires audio
            return True
        else:
            logger.error("❌ Whisper not ready after initialization")
            return False
                
    except Exception as e:
        logger.error(f"❌ Windows Whisper test failed: {e}")
        return False

async def test_windows_tts():
    """Test Windows TTS integration"""
    logger.info("🔊 Testing Windows TTS...")
    
    try:
        from windows_pipecat_integration import WindowsTTSService
        
        # Initialize service
        tts_service = WindowsTTSService()
        
        # Test synthesis
        audio_data = await tts_service._synthesize_speech("Hello, this is a test of Windows text to speech.")
        
        if audio_data and len(audio_data) > 0:
            logger.info(f"✅ TTS generated {len(audio_data)} bytes of audio")
            return True
        else:
            logger.error("❌ TTS generated no audio")
            return False
                
    except Exception as e:
        logger.error(f"❌ Windows TTS test failed: {e}")
        return False

async def test_full_handler():
    """Test the full Windows Discord handler"""
    logger.info("🔗 Testing Windows Discord Handler...")
    
    try:
        from windows_pipecat_integration import WindowsDiscordVoiceHandler
        
        # Mock Discord objects
        class MockVoiceClient:
            def __init__(self):
                self.channel = MockChannel()
                
            def is_connected(self):
                return True
        
        class MockChannel:
            def __init__(self):
                self.name = "test-channel"
                
        class MockTextChannel:
            async def send(self, text):
                logger.info(f"Would send to Discord: {text[:100]}...")
        
        # Create handler
        handler = WindowsDiscordVoiceHandler(
            voice_client=MockVoiceClient(),
            text_channel=MockTextChannel()
        )
        
        # Initialize
        await handler.initialize()
        
        # Test text processing
        response = await handler.process_text_message("Hello, how are you?", "TestUser")
        
        if response and response.strip():
            logger.info(f"✅ Handler response: {response[:100]}...")
            return True
        else:
            logger.error("❌ Handler generated no response")
            return False
                
    except Exception as e:
        logger.error(f"❌ Windows Handler test failed: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("🚀 Starting Windows Integration Tests...")
    
    tests = [
        ("Windows Phi-3 LLM", test_windows_phi3),
        ("Windows Whisper STT", test_windows_whisper),
        ("Windows TTS", test_windows_tts),
        ("Full Discord Handler", test_full_handler),
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
        logger.info("🎉 All tests passed! Windows integration ready for Discord.")
    elif passed > 0:
        logger.info("⚠️  Some tests passed. Partial functionality available.")
    else:
        logger.info("❌ All tests failed. Check Windows model installations.")

if __name__ == "__main__":
    asyncio.run(main())