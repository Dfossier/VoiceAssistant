#!/usr/bin/env python3
"""
Check PyNaCl and Opus installation
"""
import sys
import os

print("=== PyNaCl and Opus Check ===")

# Check PyNaCl
try:
    import nacl
    print(f"✅ PyNaCl version: {nacl.__version__}")
    
    # Check if PyNaCl has Opus support
    try:
        from nacl import bindings
        print("✅ PyNaCl bindings available")
    except ImportError as e:
        print(f"❌ PyNaCl bindings error: {e}")
        
except ImportError as e:
    print(f"❌ PyNaCl not installed: {e}")

# Check Discord.py Opus
try:
    import discord
    print(f"✅ Discord.py version: {discord.__version__}")
    
    print(f"Opus loaded: {discord.opus.is_loaded()}")
    
    # Try to find where PyNaCl stores its libraries
    import site
    site_packages = site.getsitepackages()
    for sp in site_packages:
        nacl_path = os.path.join(sp, 'nacl')
        if os.path.exists(nacl_path):
            print(f"📁 PyNaCl location: {nacl_path}")
            
            # Look for DLL files
            for root, dirs, files in os.walk(nacl_path):
                for file in files:
                    if file.endswith('.dll'):
                        dll_path = os.path.join(root, file)
                        print(f"🔍 Found DLL: {dll_path}")
                        
except Exception as e:
    print(f"❌ Discord check error: {e}")

# Check current working directory
print(f"📁 Current directory: {os.getcwd()}")
dll_files = [f for f in os.listdir('.') if f.endswith('.dll')]
print(f"🔍 DLL files in current dir: {dll_files}")