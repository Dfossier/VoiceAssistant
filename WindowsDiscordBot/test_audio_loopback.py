#!/usr/bin/env python3
"""
Test system audio loopback devices on Windows
"""

import sounddevice as sd
import sys

print("🔍 Searching for audio loopback devices...")
print("=" * 60)

devices = sd.query_devices()

print(f"Total devices found: {len(devices)}\n")

# Look for loopback devices
loopback_devices = []

for i, device in enumerate(devices):
    device_name = device['name'].lower()
    
    # Common patterns for loopback devices
    if any(keyword in device_name for keyword in ['stereo mix', 'what u hear', 'loopback', 'wave out', 'wasapi']):
        loopback_devices.append((i, device))
        
    # Print all devices for manual inspection
    print(f"[{i}] {device['name']}")
    print(f"    Channels: {device['max_input_channels']} in / {device['max_output_channels']} out")
    print(f"    Default Sample Rate: {device['default_samplerate']}")
    print(f"    Host API: {sd.query_hostapis()[device['hostapi']]['name']}")
    print()

print("=" * 60)

if loopback_devices:
    print("✅ Found potential loopback devices:")
    for idx, device in loopback_devices:
        print(f"  [{idx}] {device['name']}")
    print("\nTo use: Set device_index={idx} in audio capture")
else:
    print("❌ No obvious loopback devices found")
    print("\n💡 To enable system audio capture on Windows:")
    print("1. Right-click speaker icon → Sounds")
    print("2. Recording tab → Right-click → Show Disabled Devices")
    print("3. Enable 'Stereo Mix' or 'What U Hear'")
    print("4. Set as Default Device")