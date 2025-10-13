#!/usr/bin/env python3
"""Debug Kokoro audio properties"""

import wave
import numpy as np

def analyze_wav_file(filename):
    """Analyze WAV file properties"""
    try:
        with wave.open(filename, 'rb') as wav:
            frames = wav.getnframes()
            sample_rate = wav.getframerate()
            channels = wav.getnchannels()
            sampwidth = wav.getsampwidth()
            duration = frames / sample_rate
            
            print(f"\n📊 {filename} analysis:")
            print(f"  Sample rate: {sample_rate} Hz")
            print(f"  Channels: {channels}")
            print(f"  Sample width: {sampwidth} bytes ({sampwidth * 8}-bit)")
            print(f"  Frames: {frames}")
            print(f"  Duration: {duration:.2f} seconds")
            print(f"  File size: {frames * channels * sampwidth} bytes")
            
            # Read audio data for amplitude analysis
            audio_data = wav.readframes(frames)
            if sampwidth == 2:
                samples = np.frombuffer(audio_data, dtype=np.int16)
                max_amplitude = np.max(np.abs(samples))
                rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))
                print(f"  Max amplitude: {max_amplitude} / 32767 ({max_amplitude/32767*100:.1f}%)")
                print(f"  RMS amplitude: {rms:.1f}")
                
                # Check for silence
                if max_amplitude < 100:
                    print(f"  ⚠️ Very quiet audio (max < 100)")
                elif max_amplitude < 1000:
                    print(f"  ⚠️ Quiet audio (max < 1000)")
                else:
                    print(f"  ✅ Good audio levels")
            
    except Exception as e:
        print(f"❌ Error analyzing {filename}: {e}")

if __name__ == "__main__":
    # Analyze existing WAV files
    import os
    wav_files = [f for f in os.listdir('.') if f.endswith('.wav')]
    
    for wav_file in wav_files:
        analyze_wav_file(wav_file)
    
    print("\n🔧 Discord requirements:")
    print("  - Sample rate: Any (Discord converts to 48kHz)")
    print("  - Channels: 1 or 2 (Discord converts to stereo)")  
    print("  - Format: 16-bit PCM")
    print("  - Volume: Should be audible (> 1000 amplitude)")