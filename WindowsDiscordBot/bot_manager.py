"""Bot Manager - Handles graceful shutdown and restart"""
import os
import sys
import subprocess
import signal
import asyncio
import psutil
from pathlib import Path

class BotManager:
    def __init__(self):
        self.bot_process = None
        self.pid_file = Path("bot.pid")
        
    def start_bot(self):
        """Start the Discord bot"""
        print("🚀 Starting Discord Bot...")
        
        # Kill any existing bot processes
        self.kill_existing_bot()
        
        # Start new bot process
        if sys.platform == "win32":
            # Windows
            self.bot_process = subprocess.Popen(
                [sys.executable, "bot.py"],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            # Linux/WSL
            self.bot_process = subprocess.Popen([sys.executable, "bot.py"])
        
        # Save PID
        with open(self.pid_file, "w") as f:
            f.write(str(self.bot_process.pid))
        
        print(f"✅ Bot started with PID: {self.bot_process.pid}")
        return self.bot_process
    
    def kill_existing_bot(self):
        """Kill any existing bot processes"""
        # Check PID file
        if self.pid_file.exists():
            try:
                with open(self.pid_file, "r") as f:
                    old_pid = int(f.read().strip())
                
                # Try to terminate old process
                try:
                    old_process = psutil.Process(old_pid)
                    if old_process.is_running():
                        print(f"🔄 Terminating old bot process (PID: {old_pid})...")
                        old_process.terminate()
                        try:
                            old_process.wait(timeout=5)
                        except psutil.TimeoutExpired:
                            print("⚠️ Process didn't terminate, killing forcefully...")
                            old_process.kill()
                except psutil.NoSuchProcess:
                    pass
                
                # Remove PID file
                self.pid_file.unlink()
            except Exception as e:
                print(f"⚠️ Error killing old process: {e}")
        
        # Also check for any Python processes running bot.py
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and 'bot.py' in ' '.join(proc.info['cmdline']):
                    print(f"🔄 Found bot process (PID: {proc.pid}), terminating...")
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    
    def restart_bot(self):
        """Restart the bot"""
        print("🔄 Restarting Discord Bot...")
        self.kill_existing_bot()
        return self.start_bot()
    
    def monitor_bot(self):
        """Monitor bot and restart if it crashes"""
        while True:
            bot_process = self.start_bot()
            
            try:
                # Wait for bot to exit
                bot_process.wait()
                print("⚠️ Bot exited, restarting in 5 seconds...")
                asyncio.run(asyncio.sleep(5))
            except KeyboardInterrupt:
                print("\n🛑 Shutting down bot manager...")
                self.kill_existing_bot()
                break

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Discord Bot Manager")
    parser.add_argument("action", choices=["start", "stop", "restart", "monitor"],
                       help="Action to perform")
    
    args = parser.parse_args()
    manager = BotManager()
    
    if args.action == "start":
        manager.start_bot()
        print("Bot started. Use 'python bot_manager.py stop' to stop it.")
    elif args.action == "stop":
        manager.kill_existing_bot()
        print("✅ Bot stopped.")
    elif args.action == "restart":
        manager.restart_bot()
        print("✅ Bot restarted.")
    elif args.action == "monitor":
        print("📊 Starting bot monitor (auto-restart on crash)...")
        manager.monitor_bot()