#!/usr/bin/env python3
"""
HTTPS server for mobile microphone access
"""
import ssl
import os
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import the mobile app
from run_mobile import app
import uvicorn

def create_self_signed_cert():
    """Use existing certificate"""
    cert_file = "cert.pem"
    key_file = "key.pem"
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        print("✅ Using existing SSL certificate")
    else:
        print("❌ SSL certificate not found!")
        print("Run: openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365 -subj '/C=US/ST=State/L=City/O=LocalAI/CN=localhost'")
        sys.exit(1)
    
    return cert_file, key_file

if __name__ == "__main__":
    # Create certificate
    cert_file, key_file = create_self_signed_cert()
    
    print("🔒 Starting HTTPS server for mobile access...")
    print("=" * 50)
    print("⚠️  IMPORTANT: You'll get a security warning - that's normal!")
    print("    Click 'Advanced' → 'Proceed to site' to continue")
    print("=" * 50)
    print("")
    print("📱 Access from your phone:")
    print(f"   https://[YOUR_WINDOWS_IP]:8443")
    print("")
    print("🎤 This enables microphone access on mobile!")
    print("=" * 50)
    
    # Run HTTPS server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8443,
        ssl_keyfile=key_file,
        ssl_certfile=cert_file,
        log_level="info"
    )