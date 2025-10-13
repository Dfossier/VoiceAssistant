#!/usr/bin/env python3
import urllib.request
import os

# Direct download of a working Opus DLL
opus_url = "https://github.com/Rapptz/discord.py/files/4031616/libopus-0.x64.dll.zip"

print("Downloading Opus DLL...")
try:
    urllib.request.urlretrieve(opus_url, "libopus.zip")
    
    import zipfile
    with zipfile.ZipFile("libopus.zip", 'r') as z:
        z.extractall()
        print("Extracted files:", z.namelist())
    
    # Clean up zip
    os.remove("libopus.zip")
    print("✅ Opus DLL downloaded successfully!")
    
except Exception as e:
    print(f"Download failed: {e}")
    print("\nManual steps:")
    print("1. Download opus.dll from: https://www.dll-files.com/opus.dll.html")
    print("2. Choose the 64-bit version")  
    print("3. Place it in this directory")
    print("4. Name it exactly: opus.dll")