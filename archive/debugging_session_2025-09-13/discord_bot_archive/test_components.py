#!/usr/bin/env python3
"""
Test individual bot components
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_tts():
    """Test Text-to-Speech with OpenAI"""
    print("\n🗣️ Testing Text-to-Speech (OpenAI)")
    print("-" * 40)
    
    try:
        from openai import AsyncOpenAI
        
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("❌ No OPENAI_API_KEY found")
            return
        
        client = AsyncOpenAI(api_key=api_key)
        
        # Generate speech
        print("🔄 Generating speech...")
        response = await client.audio.speech.create(
            model="tts-1",
            voice="alloy", 
            input="Hello from WSL2! This is a text to speech test.",
            response_format="wav"
        )
        
        # Save to file
        test_file = "/tmp/tts_test.wav"
        with open(test_file, "wb") as f:
            f.write(response.content)
        
        file_size = len(response.content)
        print(f"✅ TTS generated: {file_size} bytes")
        print(f"📁 Saved to: {test_file}")
        
        # Test playback with ffmpeg
        import subprocess
        try:
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ FFmpeg available for audio playback")
            else:
                print("❌ FFmpeg not found")
        except FileNotFoundError:
            print("❌ FFmpeg not installed")
            print("💡 Install: sudo apt-get install ffmpeg")
        
    except Exception as e:
        print(f"❌ TTS Error: {e}")

async def test_stt():
    """Test Speech-to-Text with OpenAI"""
    print("\n🎤 Testing Speech-to-Text (OpenAI Whisper)")
    print("-" * 40)
    
    try:
        from openai import AsyncOpenAI
        
        api_key = os.getenv('OPENAI_API_KEY') 
        if not api_key:
            print("❌ No OPENAI_API_KEY found")
            return
        
        client = AsyncOpenAI(api_key=api_key)
        
        # For testing, we'd need a sample audio file
        # Check if we have the TTS output to test with
        test_file = "/tmp/tts_test.wav"
        if os.path.exists(test_file):
            print(f"🔄 Transcribing test file: {test_file}")
            
            with open(test_file, "rb") as audio_file:
                transcript = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            
            print(f"✅ Transcription: '{transcript.strip()}'")
        else:
            print("⚠️ No test audio file available")
            print("💡 Run TTS test first to generate audio")
        
    except Exception as e:
        print(f"❌ STT Error: {e}")

def test_vad():
    """Test Voice Activity Detection"""
    print("\n📡 Testing Voice Activity Detection")
    print("-" * 40)
    
    try:
        # Test simple RMS VAD
        import numpy as np
        
        # Create test audio samples
        sample_rate = 48000
        duration = 1  # 1 second
        
        # Generate silence
        silence = np.zeros(sample_rate * duration, dtype=np.int16)
        
        # Generate noise (speech simulation)
        t = np.linspace(0, duration, sample_rate * duration)
        speech = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)  # 440Hz tone
        
        from simple_wsl_bot import SimpleVAD
        vad = SimpleVAD(threshold=0.01)
        
        silence_detected = vad.detect_speech(silence.tobytes())
        speech_detected = vad.detect_speech(speech.tobytes())
        
        print(f"Silence detection: {silence_detected} (should be False)")
        print(f"Speech detection: {speech_detected} (should be True)")
        
        if not silence_detected and speech_detected:
            print("✅ VAD working correctly")
        else:
            print("⚠️ VAD may need threshold adjustment")
        
    except ImportError:
        print("❌ NumPy not available")
        print("💡 Install: pip install numpy")
    except Exception as e:
        print(f"❌ VAD Error: {e}")

def test_audio_system():
    """Test audio system components"""
    print("\n🔊 Testing Audio System")
    print("-" * 40)
    
    # Test sounddevice
    try:
        import sounddevice as sd
        print("✅ sounddevice available")
        
        # List audio devices
        devices = sd.query_devices()
        print(f"📱 Found {len(devices)} audio devices")
        
        # Check default devices
        try:
            default_input = sd.default.device[0]
            default_output = sd.default.device[1] 
            print(f"🎤 Default input: {devices[default_input]['name']}")
            print(f"🔊 Default output: {devices[default_output]['name']}")
        except Exception as e:
            print(f"⚠️ Default device issue: {e}")
        
    except ImportError:
        print("❌ sounddevice not available")
        print("💡 Install: pip install sounddevice")
    except Exception as e:
        print(f"❌ Audio system error: {e}")
    
    # Test ALSA/PulseAudio in WSL2
    import subprocess
    try:
        # Check for audio services
        result = subprocess.run(["pulseaudio", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ PulseAudio available")
        else:
            print("⚠️ PulseAudio not found")
    except FileNotFoundError:
        print("⚠️ PulseAudio not installed")
        print("💡 Install: sudo apt-get install pulseaudio")

async def test_discord_integration():
    """Test Discord-specific components"""
    print("\n🤖 Testing Discord Integration")
    print("-" * 40)
    
    try:
        import discord
        print(f"✅ Discord.py version: {discord.__version__}")
        
        # Test Opus
        discord.opus._load_default()
        opus_loaded = discord.opus.is_loaded()
        print(f"🎵 Opus loaded: {'✅' if opus_loaded else '❌'}")
        
        if not opus_loaded:
            print("❌ Opus loading failed")
            print("💡 This would cause voice connection issues")
        
        # Test FFmpeg for Discord
        try:
            audio_source = discord.FFmpegPCMAudio("/dev/null")
            print("✅ FFmpeg integration working")
        except Exception as e:
            print(f"⚠️ FFmpeg integration issue: {e}")
        
    except Exception as e:
        print(f"❌ Discord integration error: {e}")

async def test_kokoro_models():
    """Test Kokoro TTS model availability"""
    print("\n🎪 Testing Kokoro Models")
    print("-" * 40)
    
    try:
        # Check model files
        models_path = Path("/mnt/c/users/dfoss/desktop/localaimodels/kokoro-tts")
        
        if models_path.exists():
            print(f"✅ Kokoro directory found: {models_path}")
            
            main_model = models_path / "kokoro-v1_0.pth"
            voices_dir = models_path / "voices"
            
            print(f"📁 Main model: {'✅' if main_model.exists() else '❌'}")
            print(f"🎵 Voices directory: {'✅' if voices_dir.exists() else '❌'}")
            
            if voices_dir.exists():
                voices = list(voices_dir.glob("*.pt"))
                print(f"🎤 Found {len(voices)} voice files")
                if voices:
                    print("Sample voices:", [v.stem for v in voices[:5]])
            
            # Test PyTorch loading
            try:
                import torch
                print(f"✅ PyTorch available: {torch.__version__}")
                
                if main_model.exists():
                    print("🔄 Testing model loading...")
                    # Don't actually load to save time/memory
                    print("⏭️ Model loading test skipped (use real test when needed)")
                else:
                    print("❌ Main model file missing")
                    
            except ImportError:
                print("❌ PyTorch not available")
                print("💡 Install: pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu")
        else:
            print("❌ Kokoro directory not found")
            
    except Exception as e:
        print(f"❌ Kokoro test error: {e}")

async def main():
    """Run all tests"""
    print("🧪 Bot Component Testing")
    print("=" * 50)
    
    # Load environment
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print("✅ Environment loaded")
    else:
        print("⚠️ No .env file found")
    
    # Run tests
    await test_tts()
    await test_stt()
    test_vad()
    test_audio_system()
    await test_discord_integration()
    await test_kokoro_models()
    
    print("\n🎯 Test Summary:")
    print("- TTS: OpenAI API fallback")
    print("- STT: OpenAI Whisper API fallback") 
    print("- VAD: Simple RMS-based detection")
    print("- Local models: Available but need dependencies")

if __name__ == "__main__":
    asyncio.run(main())