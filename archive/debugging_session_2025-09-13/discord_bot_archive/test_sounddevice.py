#!/usr/bin/env python3
import sys
print(f"Python: {sys.version}")

try:
    import sounddevice as sd
    print(f"✅ sounddevice version: {sd.__version__}")
    
    # List audio devices
    print("\n🔍 Audio devices:")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        print(f"  {i}: {device['name']} - {device['hostapi']}")
        
    # Get default devices
    default_input = sd.default.device[0] 
    default_output = sd.default.device[1]
    print(f"\n🎤 Default input device: {default_input}")
    print(f"🔊 Default output device: {default_output}")
    
except ImportError as e:
    print(f"❌ sounddevice import failed: {e}")
    
try:
    import numpy as np
    print(f"✅ numpy version: {np.__version__}")
except ImportError as e:
    print(f"❌ numpy import failed: {e}")