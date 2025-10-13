#!/usr/bin/env python3
"""Test audio library installations"""

print("=== Testing Audio Libraries ===")

# Test sounddevice
try:
    import sounddevice as sd
    print(f"✅ sounddevice: {sd.__version__}")
    devices = sd.query_devices()
    print(f"   Found {len(devices)} audio devices")
except Exception as e:
    print(f"❌ sounddevice: {e}")

# Test numpy
try:
    import numpy as np
    print(f"✅ numpy: {np.__version__}")
except Exception as e:
    print(f"❌ numpy: {e}")

# Test pyaudio
try:
    import pyaudio
    audio = pyaudio.PyAudio()
    device_count = audio.get_device_count()
    print(f"✅ pyaudio: Found {device_count} audio devices")
    audio.terminate()
except Exception as e:
    print(f"❌ pyaudio: {e}")

# Test wave module
try:
    import wave
    print("✅ wave: Available")
except Exception as e:
    print(f"❌ wave: {e}")

print("\n=== Installation Commands ===")
print("For sounddevice: pip install sounddevice")
print("For PyAudio: pip install pyaudio")
print("For numpy: pip install numpy")