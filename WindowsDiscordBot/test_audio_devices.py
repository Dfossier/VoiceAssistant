import sounddevice as sd
import numpy as np
import time

def list_audio_devices():
    """List all available audio input devices"""
    print("Available Audio Input Devices:")
    print("=" * 50)
    
    devices = sd.query_devices()
    input_devices = []
    
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            input_devices.append((i, device))
            status = " (DEFAULT)" if i == sd.default.device[0] else ""
            print(f"{i:2d}: {device['name']}{status}")
            print(f"    Channels: {device['max_input_channels']}, Sample Rate: {device['default_samplerate']}")
    
    return input_devices

def test_device(device_id, duration=3):
    """Test recording from a specific device"""
    print(f"\nTesting device {device_id} for {duration} seconds...")
    print("Please speak into your microphone now!")
    
    try:
        sample_rate = 16000
        audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate, 
                           channels=1, device=device_id, dtype=np.float32)
        sd.wait()  # Wait for recording to complete
        
        # Calculate audio levels
        rms = np.sqrt(np.mean(audio_data**2))
        db_level = 20 * np.log10(rms) if rms > 0 else -100
        max_level = np.max(np.abs(audio_data))
        
        print(f"   RMS Level: {rms:.6f}")
        print(f"   dB Level:  {db_level:.1f} dB")
        print(f"   Max Level: {max_level:.3f}")
        
        # Assessment
        if db_level > -40:
            print("   GOOD - Strong audio signal")
        elif db_level > -60:
            print("   WEAK - Low but usable signal")
        else:
            print("   POOR - Too quiet or no signal")
            
        return db_level
        
    except Exception as e:
        print(f"   ERROR: {e}")
        return None

if __name__ == "__main__":
    print("Audio Device Diagnostic Tool")
    print("=" * 40)
    
    # List all devices
    input_devices = list_audio_devices()
    
    if not input_devices:
        print("No input devices found!")
        exit(1)
    
    print(f"\nCurrent default input device: {sd.default.device[0]}")
    
    # Test each device
    best_device = None
    best_level = -999
    
    for device_id, device_info in input_devices:
        level = test_device(device_id)
        if level and level > best_level:
            best_level = level
            best_device = device_id
    
    print(f"\nRECOMMENDATION:")
    if best_device is not None:
        device_name = sd.query_devices(best_device)['name']
        print(f"   Use device {best_device}: {device_name}")
        print(f"   Best level: {best_level:.1f} dB")
        
        if best_device != sd.default.device[0]:
            print(f"\nCHANGE NEEDED:")
            print(f"   Current default: {sd.default.device[0]}")
            print(f"   Recommended:     {best_device}")
    else:
        print("   No suitable device found - check microphone connections")