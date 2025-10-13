#!/usr/bin/env python3
"""
Test script for the Kokoro TTS wrapper
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.kokoro_wrapper import create_kokoro_tts

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_kokoro_wrapper():
    """Test the Kokoro TTS wrapper with various texts"""
    
    logger.info("Testing Kokoro TTS wrapper...")
    
    # Create TTS instance
    tts = create_kokoro_tts(
        model_path="/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts",
        voice_name="af_sarah"
    )
    
    # Test texts
    test_texts = [
        "Hello! This is a test of the Kokoro text to speech system.",
        "The quick brown fox jumps over the lazy dog.",
        "Testing one, two, three. Can you hear me clearly?",
        "This wrapper gracefully falls back to Windows TTS if needed."
    ]
    
    for i, text in enumerate(test_texts, 1):
        logger.info(f"\nTest {i}: '{text}'")
        
        try:
            # Synthesize speech
            audio_bytes, sample_rate = await tts.synthesize_speech(text)
            
            if audio_bytes:
                logger.info(f"✅ Success! Generated {len(audio_bytes)} bytes at {sample_rate}Hz")
                
                # Optionally save to file for testing
                output_file = f"test_output_{i}.raw"
                with open(output_file, 'wb') as f:
                    f.write(audio_bytes)
                logger.info(f"   Saved to {output_file}")
            else:
                logger.error(f"❌ Failed to generate audio")
                
        except Exception as e:
            logger.error(f"❌ Error: {e}")
    
    logger.info("\nTesting complete!")


async def test_direct_kokoro():
    """Test direct Kokoro implementation"""
    from src.core.kokoro_wrapper import SimpleKokoroTTS
    
    logger.info("\nTesting direct Kokoro implementation...")
    
    try:
        kokoro = SimpleKokoroTTS(
            model_path="/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts",
            voice_name="af_sarah"
        )
        
        text = "Testing direct Kokoro implementation"
        result = kokoro.synthesize(text)
        
        if result is not None:
            logger.info("✅ Direct Kokoro test passed")
        else:
            logger.info("ℹ️ Direct Kokoro returned None (expected for simplified implementation)")
            
    except Exception as e:
        logger.error(f"Direct Kokoro test failed: {e}")


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_kokoro_wrapper())
    asyncio.run(test_direct_kokoro())