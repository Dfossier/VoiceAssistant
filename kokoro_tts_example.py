#!/usr/bin/env python3
"""
Example: Using Kokoro TTS without espeak/phonemizer dependencies

This example shows how to use the Kokoro TTS integration that automatically
handles the espeak dependency issues by:
1. Using a simplified phoneme conversion (no espeak required)
2. Falling back to Windows SAPI TTS when needed
3. Providing seamless TTS functionality
"""

import asyncio
import logging
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from src.core.kokoro_integration import create_kokoro_tts_integration

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Example usage of Kokoro TTS integration"""
    
    logger.info("=== Kokoro TTS Integration Example ===\n")
    
    # Create TTS instance
    tts = create_kokoro_tts_integration(
        model_path="/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts",
        voice_name="af_sarah"  # Female voice
    )
    
    # Show available voices
    voices = tts.get_available_voices()
    logger.info(f"Available voices ({len(voices)} total):")
    for i, voice in enumerate(voices[:10]):
        logger.info(f"  - {voice}")
    if len(voices) > 10:
        logger.info(f"  ... and {len(voices) - 10} more")
    
    logger.info("")
    
    # Example texts
    example_texts = [
        "Welcome to the Kokoro text to speech system!",
        "This implementation works without espeak or phonemizer dependencies.",
        "It uses a simplified approach that gracefully falls back to Windows TTS.",
        "Perfect for Discord bots and voice assistants!"
    ]
    
    # Process each text
    for i, text in enumerate(example_texts, 1):
        logger.info(f"Example {i}: \"{text}\"")
        
        # Synthesize speech
        audio_bytes, sample_rate = await tts.synthesize(text)
        
        if audio_bytes:
            # Calculate duration
            duration = len(audio_bytes) / (sample_rate * 2)  # 16-bit = 2 bytes per sample
            logger.info(f"  ✅ Generated {len(audio_bytes):,} bytes ({duration:.1f} seconds) at {sample_rate}Hz")
            
            # Save to file (optional)
            output_file = f"kokoro_example_{i}.raw"
            with open(output_file, 'wb') as f:
                f.write(audio_bytes)
            logger.info(f"  💾 Saved to {output_file}")
        else:
            logger.error(f"  ❌ Failed to generate audio")
        
        logger.info("")
    
    # Try different voices
    logger.info("=== Testing Different Voices ===")
    test_text = "Hello, this is a voice test."
    
    test_voices = ["af_bella", "af_nova", "am_adam", "bm_george"]
    for voice in test_voices:
        if voice in voices:
            tts.set_voice(voice)
            logger.info(f"\nVoice: {voice}")
            
            audio_bytes, sample_rate = await tts.synthesize(test_text)
            if audio_bytes:
                logger.info(f"  ✅ Generated {len(audio_bytes):,} bytes")
            else:
                logger.info(f"  ❌ Failed")
    
    logger.info("\n=== Integration with Discord/Pipecat ===")
    logger.info("To use in your Discord bot or Pipecat pipeline:")
    logger.info("")
    logger.info("```python")
    logger.info("from src.core.kokoro_integration import create_kokoro_tts_integration")
    logger.info("")
    logger.info("# In your bot/pipeline initialization:")
    logger.info("tts = create_kokoro_tts_integration()")
    logger.info("")
    logger.info("# When you need TTS:")
    logger.info("audio_bytes, sample_rate = await tts.synthesize('Your text here')")
    logger.info("```")
    logger.info("")
    logger.info("✅ No espeak or phonemizer required!")
    logger.info("✅ Automatic fallback to Windows TTS!")
    logger.info("✅ 54 high-quality voices available!")


if __name__ == "__main__":
    asyncio.run(main())