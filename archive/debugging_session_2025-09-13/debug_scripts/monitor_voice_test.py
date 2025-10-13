#!/usr/bin/env python3
"""Monitor logs during voice connection testing"""

import time
import subprocess
import sys
from pathlib import Path

def tail_logs():
    """Monitor both backend and bot logs in real-time"""
    backend_log = Path("/mnt/c/users/dfoss/desktop/localaimodels/assistant/backend.log")
    bot_log = Path("/mnt/c/users/dfoss/desktop/localaimodels/Assistant/DiscordBot/bot.log")
    
    print("🔍 Monitoring logs for voice connection testing...")
    print("📋 Use Ctrl+C to stop monitoring")
    print("=" * 60)
    print()
    
    try:
        # Start monitoring both logs
        backend_process = subprocess.Popen(
            ['tail', '-f', str(backend_log)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        bot_process = subprocess.Popen(
            ['tail', '-f', str(bot_log)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        print("🎤 Now use Discord command: !join")
        print("   (In your Discord server where the bot is connected)")
        print()
        
        # Monitor both logs
        while True:
            # Check backend log
            if backend_process.poll() is None:
                backend_process.stdout.settimeout(0.1)
                try:
                    line = backend_process.stdout.readline()
                    if line:
                        print(f"📊 BACKEND: {line.rstrip()}")
                except:
                    pass
            
            # Check bot log
            if bot_process.poll() is None:
                bot_process.stdout.settimeout(0.1)
                try:
                    line = bot_process.stdout.readline()
                    if line:
                        print(f"🤖 BOT: {line.rstrip()}")
                        # Look for specific error patterns
                        if "4006" in line:
                            print("⚠️  4006 ERROR DETECTED - Session no longer valid")
                        elif "ConnectionClosed" in line:
                            print("⚠️  CONNECTION ERROR DETECTED")
                        elif "Voice connection successful" in line:
                            print("✅ VOICE CONNECTION SUCCESS!")
                        elif "Failed to connect" in line:
                            print("❌ VOICE CONNECTION FAILED")
                except:
                    pass
                    
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping log monitoring...")
        backend_process.terminate()
        bot_process.terminate()
        print("✅ Log monitoring stopped")

if __name__ == "__main__":
    tail_logs()