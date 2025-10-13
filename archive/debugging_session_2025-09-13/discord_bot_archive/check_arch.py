#!/usr/bin/env python3
import platform
import sys
import struct

print("=== Python Architecture Info ===")
print(f"Python version: {sys.version}")
print(f"Architecture: {platform.architecture()}")
print(f"Machine type: {platform.machine()}")
print(f"Processor: {platform.processor()}")
print(f"Platform: {platform.platform()}")
print(f"Pointer size: {struct.calcsize('P') * 8}-bit")

# Check if we're running 64-bit Python
if struct.calcsize('P') == 8:
    print("✅ Running 64-bit Python - need 64-bit opus.dll")
else:
    print("✅ Running 32-bit Python - need 32-bit opus.dll")