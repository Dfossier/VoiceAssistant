#!/usr/bin/env python3
"""
Basic Smart Turn VAD v3 Testing
Tests Smart Turn functionality independently before integration
"""

import asyncio
import sys
import time
import wave
import numpy as np
from pathlib import Path
from loguru import logger

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_smart_turn_installation():
    """Test if Smart Turn v3 can be imported and initialized"""
    try:
        from pipecat.analyzers.smart_turn import LocalSmartTurnAnalyzerV3
        logger.info("✅ Smart Turn v3 import successful")
        
        # Initialize analyzer
        analyzer = LocalSmartTurnAnalyzerV3()
        logger.info("✅ Smart Turn analyzer initialized")
        
        return analyzer
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.info("💡 Try: pip install 'pipecat-ai[local-smart-turn-v3]==0.0.85'")
        return None
    except Exception as e:
        logger.error(f"❌ Initialization error: {e}")
        return None

def load_test_audio(file_path: str) -> tuple[bytes, int]:
    """Load WAV file and return PCM data + sample rate"""
    try:
        with wave.open(file_path, 'rb') as wav_file:
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            frames = wav_file.readframes(wav_file.getnframes())
            
            logger.info(f"📊 Loaded audio: {sample_rate}Hz, {channels}ch, {len(frames)} bytes")
            
            # Convert to 16kHz mono if needed (Smart Turn requirement)
            if sample_rate != 16000 or channels != 1:
                logger.info("🔄 Converting to 16kHz mono for Smart Turn...")
                
                # Convert to numpy array
                if wav_file.getsampwidth() == 2:  # 16-bit
                    audio_array = np.frombuffer(frames, dtype=np.int16)
                else:
                    logger.warning("⚠️ Unsupported sample width, using as-is")
                    return frames, sample_rate
                
                # Convert stereo to mono if needed
                if channels == 2:
                    audio_array = audio_array.reshape(-1, 2).mean(axis=1).astype(np.int16)
                
                # Resample if needed (simple approach)
                if sample_rate != 16000:
                    # Simple resampling (for testing only)
                    target_length = int(len(audio_array) * 16000 / sample_rate)
                    audio_array = np.interp(
                        np.linspace(0, len(audio_array), target_length),
                        np.arange(len(audio_array)),
                        audio_array
                    ).astype(np.int16)
                
                frames = audio_array.tobytes()
                sample_rate = 16000
                logger.info(f"✅ Converted to: {sample_rate}Hz, 1ch, {len(frames)} bytes")
            
            return frames, sample_rate
            
    except FileNotFoundError:
        logger.error(f"❌ Audio file not found: {file_path}")
        return b"", 0
    except Exception as e:
        logger.error(f"❌ Error loading audio: {e}")
        return b"", 0

async def test_smart_turn_detection(analyzer, audio_data: bytes, sample_rate: int):
    """Test Smart Turn detection on audio data"""
    try:
        logger.info("🎯 Testing Smart Turn detection...")
        
        start_time = time.time()
        
        # Smart Turn expects specific format - let's check documentation
        # For now, try direct analysis
        result = await analyzer.analyze(audio_data)
        
        inference_time = (time.time() - start_time) * 1000  # ms
        
        logger.info(f"⚡ Smart Turn inference time: {inference_time:.1f}ms")
        logger.info(f"📊 Turn detection result: {result}")
        
        return result, inference_time
        
    except Exception as e:
        logger.error(f"❌ Smart Turn detection error: {e}")
        return None, 0

def create_test_audio() -> tuple[bytes, int]:
    """Create synthetic test audio for basic testing"""
    logger.info("🎵 Creating synthetic test audio...")
    
    # Generate 3 seconds of 16kHz mono audio with speech-like patterns
    sample_rate = 16000
    duration = 3.0
    samples = int(sample_rate * duration)
    
    # Create speech-like waveform (multiple tones + noise)
    t = np.linspace(0, duration, samples)
    
    # Fundamental frequency (like human voice)
    speech = np.sin(2 * np.pi * 150 * t) * 0.3  # ~150Hz fundamental
    speech += np.sin(2 * np.pi * 300 * t) * 0.2  # First harmonic
    speech += np.sin(2 * np.pi * 450 * t) * 0.1  # Second harmonic
    
    # Add some noise and amplitude modulation (like speech)
    speech += np.random.normal(0, 0.05, samples)
    speech *= (1 + 0.3 * np.sin(2 * np.pi * 2 * t))  # Amplitude modulation
    
    # Add pause at the end (silence for turn detection)
    pause_samples = int(0.5 * sample_rate)
    speech[-pause_samples:] = 0
    
    # Convert to 16-bit PCM
    speech_int16 = (speech * 32767).clip(-32768, 32767).astype(np.int16)
    audio_bytes = speech_int16.tobytes()
    
    logger.info(f"✅ Created {len(audio_bytes)} bytes of test audio ({duration}s)")
    return audio_bytes, sample_rate

async def benchmark_performance(analyzer, audio_data: bytes, sample_rate: int, iterations: int = 10):
    """Benchmark Smart Turn performance"""
    logger.info(f"⏱️  Benchmarking Smart Turn performance ({iterations} iterations)...")
    
    times = []
    results = []
    
    for i in range(iterations):
        start_time = time.time()
        try:
            result = await analyzer.analyze(audio_data)
            inference_time = (time.time() - start_time) * 1000
            times.append(inference_time)
            results.append(result)
            
            if i == 0:  # Log first result
                logger.info(f"🎯 Sample result: {result}")
                
        except Exception as e:
            logger.error(f"❌ Iteration {i} failed: {e}")
            continue
    
    if times:
        avg_time = np.mean(times)
        min_time = np.min(times)
        max_time = np.max(times)
        
        logger.info(f"📊 Performance Results:")
        logger.info(f"   Average: {avg_time:.1f}ms")
        logger.info(f"   Min: {min_time:.1f}ms") 
        logger.info(f"   Max: {max_time:.1f}ms")
        logger.info(f"   Target: <10ms on GPU, <60ms on CPU")
        
        if avg_time < 10:
            logger.info("🚀 Excellent! GPU-level performance achieved")
        elif avg_time < 60:
            logger.info("✅ Good! CPU-level performance achieved")
        else:
            logger.warning("⚠️ Performance slower than expected")
    else:
        logger.error("❌ No successful benchmarks")

async def main():
    """Main testing function"""
    logger.info("🎯 Smart Turn VAD v3 Basic Testing")
    logger.info("=" * 50)
    
    # Test 1: Installation and import
    logger.info("📦 Phase 1: Testing installation...")
    analyzer = await test_smart_turn_installation()
    if not analyzer:
        logger.error("❌ Cannot proceed without Smart Turn analyzer")
        return
    
    # Test 2: Create synthetic test audio
    logger.info("\n🎵 Phase 2: Creating test audio...")
    audio_data, sample_rate = create_test_audio()
    if not audio_data:
        logger.error("❌ Failed to create test audio")
        return
    
    # Test 3: Basic detection test
    logger.info("\n🎯 Phase 3: Basic turn detection test...")
    result, inference_time = await test_smart_turn_detection(analyzer, audio_data, sample_rate)
    if result is None:
        logger.error("❌ Basic detection test failed")
        return
    
    # Test 4: Performance benchmark
    logger.info("\n⏱️  Phase 4: Performance benchmarking...")
    await benchmark_performance(analyzer, audio_data, sample_rate, iterations=10)
    
    # Test 5: Try with existing audio files if available
    logger.info("\n📁 Phase 5: Testing with existing audio files...")
    test_files = [
        "archive/debugging_session_2025-09-13/audio_files/kokoro_test.wav",
        "archive/debugging_session_2025-09-13/audio_files/websocket_tts_test.wav"
    ]
    
    for test_file in test_files:
        if Path(test_file).exists():
            logger.info(f"🎵 Testing with: {test_file}")
            file_audio, file_sr = load_test_audio(test_file)
            if file_audio:
                result, time_ms = await test_smart_turn_detection(analyzer, file_audio, file_sr)
                logger.info(f"   Result: {result}, Time: {time_ms:.1f}ms")
        else:
            logger.info(f"⏭️  Skipping missing file: {test_file}")
    
    logger.info("\n✅ Smart Turn basic testing completed!")
    logger.info("🔧 Next steps:")
    logger.info("   1. Install updated requirements: pip install -r requirements.txt")
    logger.info("   2. Test integration with existing voice assistant")
    logger.info("   3. Compare with current buffering approach")

if __name__ == "__main__":
    asyncio.run(main())