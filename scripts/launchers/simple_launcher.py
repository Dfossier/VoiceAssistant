#!/usr/bin/env python3
"""
Simple Command Line Launcher for AI Assistant
No GUI dependencies - works everywhere
"""
import subprocess
import os
import sys
import time
import signal
import psutil
from pathlib import Path

class SimpleLauncher:
    def __init__(self):
        self.backend_process = None
        self.bot_process = None
        self.backend_path = Path(__file__).parent
        self.bot_path = Path(__file__).parent / "discordbot"
    
    def is_port_in_use(self, port):
        """Check if port is in use"""
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN':
                return True
        return False
    
    def is_discord_bot_running(self):
        """Check if Discord bot is running"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'bot.py' in ' '.join(cmdline):
                    return True
            except:
                pass
        return False
    
    def show_status(self):
        """Show current status"""
        print("\n" + "="*50)
        print("🤖 AI Assistant Service Status")
        print("="*50)
        
        backend_running = self.is_port_in_use(8000)
        bot_running = self.is_discord_bot_running()
        
        print(f"🔧 Backend API:    {'🟢 RUNNING' if backend_running else '⚫ STOPPED'}")
        print(f"   Port: 8000")
        print(f"   URL:  http://localhost:8000")
        print()
        print(f"🤖 Discord Bot:    {'🟢 RUNNING' if bot_running else '⚫ STOPPED'}")
        print(f"   Status: {'Connected' if bot_running else 'Disconnected'}")
        print()
        
        if backend_running and bot_running:
            print("✅ All services are running!")
        elif not backend_running and not bot_running:
            print("⚫ All services are stopped")
        else:
            print("⚠️  Some services are not running")
        print()
    
    def start_backend(self):
        """Start backend service"""
        if self.is_port_in_use(8000):
            print("⚠️  Backend is already running!")
            return
        
        print("🚀 Starting backend API...")
        
        # Use the venv python
        venv_python = self.backend_path / "venv" / "bin" / "python"
        
        # Start in background
        with open(self.backend_path / 'backend.log', 'w') as f:
            self.backend_process = subprocess.Popen(
                [str(venv_python), "discord_main.py"],
                stdout=f,
                stderr=subprocess.STDOUT,
                cwd=str(self.backend_path)
            )
        
        # Wait a moment and check if it started
        time.sleep(3)
        if self.is_port_in_use(8000):
            print("✅ Backend started successfully!")
        else:
            print("❌ Backend failed to start. Check backend.log for details.")
    
    def start_bot(self):
        """Start Discord bot"""
        if not self.bot_path.exists():
            print(f"❌ Bot directory not found: {self.bot_path}")
            return
        
        if self.is_discord_bot_running():
            print("⚠️  Discord bot is already running!")
            return
        
        print("🤖 Starting Discord bot...")
        
        # Use the venv python from the parent directory
        venv_python = self.backend_path / "venv" / "bin" / "python"
        
        # Start in background
        with open(self.bot_path / 'bot.log', 'w') as f:
            self.bot_process = subprocess.Popen(
                [str(venv_python), str(self.bot_path / "bot.py")],
                stdout=f,
                stderr=subprocess.STDOUT,
                cwd=str(self.bot_path)
            )
        
        # Wait a moment and check
        time.sleep(3)
        if self.is_discord_bot_running():
            print("✅ Discord bot started successfully!")
        else:
            print("❌ Discord bot failed to start. Check bot.log for details.")
    
    def stop_backend(self):
        """Stop backend service"""
        print("⏹️  Stopping backend...")
        
        # Kill any process on port 8000
        killed = False
        for proc in psutil.process_iter():
            try:
                for conn in proc.connections():
                    if conn.laddr.port == 8000:
                        proc.kill()
                        killed = True
                        break
            except:
                pass
        
        if killed:
            print("✅ Backend stopped")
        else:
            print("⚠️  Backend was not running")
    
    def stop_bot(self):
        """Stop Discord bot"""
        print("⏹️  Stopping Discord bot...")
        
        # Kill any bot.py processes
        killed = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'bot.py' in ' '.join(cmdline):
                    proc.kill()
                    killed = True
                    break
            except:
                pass
        
        if killed:
            print("✅ Discord bot stopped")
        else:
            print("⚠️  Discord bot was not running")
    
    def start_all(self):
        """Start all services"""
        print("🚀 Starting all services...")
        self.start_backend()
        time.sleep(2)
        self.start_bot()
    
    def stop_all(self):
        """Stop all services"""
        print("⏹️  Stopping all services...")
        self.stop_bot()
        self.stop_backend()
    
    def show_logs(self, service="both"):
        """Show recent logs"""
        print("\n📋 Recent Logs:")
        print("-" * 30)
        
        if service in ["backend", "both"]:
            backend_log = self.backend_path / "backend.log"
            if backend_log.exists():
                print("\n🔧 Backend Logs:")
                with open(backend_log) as f:
                    lines = f.readlines()
                    for line in lines[-10:]:  # Last 10 lines
                        print(f"  {line.strip()}")
        
        if service in ["bot", "both"]:
            bot_log = self.bot_path / "bot.log"
            if bot_log.exists():
                print("\n🤖 Bot Logs:")
                with open(bot_log) as f:
                    lines = f.readlines()
                    for line in lines[-10:]:  # Last 10 lines
                        print(f"  {line.strip()}")
    
    def run(self):
        """Main interactive loop"""
        while True:
            self.show_status()
            
            print("Available Commands:")
            print("1. Start All Services")
            print("2. Stop All Services")
            print("3. Start Backend Only")
            print("4. Stop Backend Only")
            print("5. Start Bot Only")
            print("6. Stop Bot Only")
            print("7. Show Logs")
            print("8. Refresh Status")
            print("9. Exit")
            print()
            
            try:
                choice = input("Enter choice (1-9): ").strip()
                
                if choice == '1':
                    self.start_all()
                elif choice == '2':
                    self.stop_all()
                elif choice == '3':
                    self.start_backend()
                elif choice == '4':
                    self.stop_backend()
                elif choice == '5':
                    self.start_bot()
                elif choice == '6':
                    self.stop_bot()
                elif choice == '7':
                    self.show_logs()
                elif choice == '8':
                    continue  # Refresh by continuing the loop
                elif choice == '9':
                    print("👋 Goodbye!")
                    break
                else:
                    print("❌ Invalid choice. Please enter 1-9.")
                
                input("\nPress Enter to continue...")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    launcher = SimpleLauncher()
    launcher.run()