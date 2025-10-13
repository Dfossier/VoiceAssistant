#!/usr/bin/env python3
"""Test Kokoro TTS audio generation and playback"""

import asyncio
import wave
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.kokoro_tts_service import kokoro_service

async def test_kokoro():
    """Test Kokoro TTS generation"""
    print("🎯 Testing Kokoro TTS...")
    
    # Initialize service
    if not await kokoro_service.initialize():
        print("❌ Failed to initialize Kokoro")
        return
        
    # Test text
    test_text = "Hello, this is a test of Kokoro text to speech."
    print(f"📝 Text: {test_text}")
    
    # Generate audio
    audio_bytes = await kokoro_service.synthesize(test_text)
    
    if audio_bytes:
        print(f"✅ Generated {len(audio_bytes)} bytes of audio")
        
        # Save to WAV file
        output_file = "kokoro_test.wav"
        with wave.open(output_file, 'wb') as wav:
            wav.setnchannels(1)  # Mono
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(24000)  # 24kHz
            wav.writeframes(audio_bytes)
            
        print(f"💾 Saved to {output_file}")
        print(f"📊 Duration: {len(audio_bytes) / (24000 * 2):.2f} seconds")
        
        # Try to play it
        try:
            import subprocess
            subprocess.run(['aplay', output_file], check=True)
            print("🔊 Played audio successfully")
        except Exception as e:
            print(f"⚠️ Could not play audio: {e}")
            print("💡 Try playing kokoro_test.wav manually")
    else:
        print("❌ Failed to generate audio")

if __name__ == "__main__":
    asyncio.run(test_kokoro())