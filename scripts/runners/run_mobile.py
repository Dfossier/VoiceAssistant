#!/usr/bin/env python3
"""
Mobile-friendly server runner with better network configuration
"""
import os
import sys
import socket
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse
    import uvicorn
    from loguru import logger
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Run: source venv/bin/activate && pip install fastapi uvicorn loguru")
    sys.exit(1)

def get_network_info():
    """Get network information for mobile access"""
    try:
        # Get WSL IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        wsl_ip = s.getsockname()[0]
        s.close()
        
        # Get Windows IP from WSL
        with open('/etc/resolv.conf', 'r') as f:
            nameserver = f.read().strip().split('\n')[-1].split()[-1]
        
        return wsl_ip, nameserver
    except:
        return "127.0.0.1", "unknown"

# Create FastAPI app
app = FastAPI(title="Local AI Assistant (Mobile)", version="0.1.0-mobile")

# Very permissive CORS for mobile testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    wsl_ip, windows_ip = get_network_info()
    return HTMLResponse(content=f"""
<!DOCTYPE html>
<html>
<head>
    <title>Local AI Assistant - Mobile Ready</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: Arial; background: #0a0a0a; color: #e5e5e5; padding: 20px; }}
        .container {{ max-width: 400px; margin: 0 auto; }}
        h1 {{ color: #60a5fa; text-align: center; }}
        .link-box {{ background: #1a1a1a; padding: 15px; margin: 10px 0; border-radius: 8px; }}
        a {{ color: #60a5fa; text-decoration: none; font-size: 18px; }}
        a:hover {{ color: #34d399; }}
        .info {{ background: #374151; padding: 10px; border-radius: 6px; margin: 10px 0; font-size: 14px; }}
        .status {{ color: #10b981; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📱 Mobile AI Assistant</h1>
        
        <div class="info">
            <div class="status">✅ Server Running</div>
            <div>WSL IP: {wsl_ip}</div>
            <div>Windows IP: {windows_ip}</div>
        </div>
        
        <div class="link-box">
            <a href="/static/conversation.html">🎙️ Voice Conversation</a>
        </div>
        
        <div class="link-box">
            <a href="/static/continuous.html">🎯 Continuous Chat</a>
        </div>
        
        <div class="link-box">
            <a href="/static/streaming-test.html">🧪 Streaming Test</a>
        </div>
        
        <div class="link-box">
            <a href="/static/simple.html">⚡ Simple Voice</a>
        </div>
        
        <div class="info">
            <strong>Mobile Access:</strong><br>
            Use your Windows IP address:<br>
            http://{windows_ip}:8000
        </div>
    </div>
</body>
</html>""")

@app.get("/health")
async def health():
    wsl_ip, windows_ip = get_network_info()
    return {
        "status": "healthy", 
        "version": "mobile", 
        "wsl_ip": wsl_ip,
        "windows_ip": windows_ip
    }

# Import WebSocket handler from minimal_main
if __name__ == "__main__":
    wsl_ip, windows_ip = get_network_info()
    
    print("📱 Mobile AI Assistant Starting...")
    print("=" * 50)
    print(f"WSL IP: {wsl_ip}")
    print(f"Windows IP: {windows_ip}")
    print("")
    print("🔧 SETUP REQUIRED for mobile access:")
    print("Run in Windows PowerShell (as Administrator):")
    print("")
    print("netsh interface portproxy add v4tov4 \\")
    print(f"  listenport=8000 listenaddress=0.0.0.0 \\")
    print(f"  connectport=8000 connectaddress={wsl_ip}")
    print("")
    print("New-NetFirewallRule -DisplayName 'AI Assistant' \\")
    print("  -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow")
    print("")
    print(f"📱 Then visit: http://{windows_ip}:8000")
    print("=" * 50)
    
    # Start server
    uvicorn.run(
        app,
        host="0.0.0.0",  # Bind to all interfaces
        port=8000,
        log_level="info"
    )