#!/usr/bin/env python3
import platform
import sys

print(f"Python version: {sys.version}")
print(f"Python architecture: {platform.architecture()}")
print(f"System: {platform.system()} {platform.release()}")
print(f"Machine: {platform.machine()}")
print(f"Processor: {platform.processor()}")