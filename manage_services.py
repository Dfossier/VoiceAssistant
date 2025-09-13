#!/usr/bin/env python3
"""Service management script for Discord bot and backend"""

import subprocess
import time
import os
import signal
import sys
from pathlib import Path

def get_processes_on_port(port):
    """Get processes using a specific port"""
    try:
        result = subprocess.run(['lsof', '-ti', f':{port}'], 
                              capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            return [int(pid) for pid in result.stdout.strip().split('\n') if pid.strip()]
    except Exception:
        pass
    return []

def is_port_listening(port):
    """Check if a port is actively listening"""
    try:
        # Use netstat to check if port is in LISTEN state
        result = subprocess.run(['netstat', '-tlnp'], 
                              capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return f':{port}' in result.stdout and 'LISTEN' in result.stdout
            
        # Fallback to ss command
        result = subprocess.run(['ss', '-tlnp'], 
                              capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return f':{port}' in result.stdout
    except Exception:
        pass
    
    # Final fallback - check with lsof
    return len(get_processes_on_port(port)) > 0

def kill_processes(pids):
    """Force kill processes by PID"""
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
            print(f"✅ Killed process {pid}")
        except ProcessLookupError:
            print(f"⚠️ Process {pid} already dead")
        except Exception as e:
            print(f"❌ Failed to kill process {pid}: {e}")

def stop_all_services():
    """Stop all Discord bot and backend services"""
    print("🛑 Stopping all services...")
    
    # Kill processes on port 8000
    port_pids = get_processes_on_port(8000)
    if port_pids:
        print(f"Found {len(port_pids)} processes on port 8000")
        kill_processes(port_pids)
    
    # Kill Python bot processes by name
    try:
        result = subprocess.run(['pkill', '-f', r'python.*bot\.py'], 
                              capture_output=True, text=True, check=False)
        if result.returncode == 0:
            print("✅ Killed bot processes")
    except Exception:
        pass
    
    # Kill Python main.py processes
    try:
        result = subprocess.run(['pkill', '-f', r'python.*main\.py'], 
                              capture_output=True, text=True, check=False)
        if result.returncode == 0:
            print("✅ Killed backend processes")
    except Exception:
        pass
    
    # Wait for cleanup
    time.sleep(2)
    
    # Verify port is free
    remaining = get_processes_on_port(8000)
    if remaining:
        print(f"⚠️ Still {len(remaining)} processes on port 8000, force killing...")
        kill_processes(remaining)
        time.sleep(1)
    
    print("✅ All services stopped")

def start_backend():
    """Start backend server"""
    print("🚀 Starting backend server...")
    
    backend_dir = Path("/mnt/c/users/dfoss/desktop/localaimodels/assistant")
    venv_python = backend_dir / "venv" / "bin" / "python"
    
    if not venv_python.exists():
        print("❌ Virtual environment not found")
        return False
    
    try:
        # Start backend in background
        subprocess.Popen([
            str(venv_python), "main.py"
        ], 
        cwd=str(backend_dir),
        stdout=open(backend_dir / "backend.log", "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True  # Detach from parent
        )
        
        # Wait for startup
        print("⏳ Waiting for backend to start...")
        
        # Check multiple times for slow startup
        log_file = backend_dir / "backend.log"
        for i in range(60):  # Wait up to 60 seconds (backend takes ~25-30s with models)
            time.sleep(1)
            
            # Check log file for successful startup
            if log_file.exists():
                try:
                    with open(log_file, "r") as f:
                        content = f.read()
                        if "Uvicorn running" in content:
                            # Also verify port is listening
                            port_pids = get_processes_on_port(8000)
                            if port_pids:
                                print(f"✅ Backend started after {i+1} seconds (PID: {port_pids[0]})")
                            else:
                                print(f"✅ Backend started after {i+1} seconds")
                            time.sleep(2)  # Give it a moment to stabilize
                            return True
                        elif "Error" in content and "critical" in content.lower():
                            print("❌ Critical error detected in backend log")
                            break
                except Exception:
                    pass  # File might be locked by writer
            
            if i == 5:
                print("   Still waiting for backend to initialize...")
            elif i == 15:
                print("   Backend is loading models (this takes time)...")
            elif i == 25:
                print("   Almost ready...")
        
        print("❌ Backend failed to start after 60 seconds")
        # Check the log for errors
        try:
            with open(backend_dir / "backend.log", "r") as f:
                last_lines = f.readlines()[-10:]
                print("   Last log lines:")
                for line in last_lines:
                    print(f"   {line.rstrip()}")
        except:
            pass
        return False
            
    except Exception as e:
        print(f"❌ Error starting backend: {e}")
        return False

def start_bot():
    """Start Discord bot"""
    print("🤖 Starting Discord bot...")
    
    bot_dir = Path("/mnt/c/users/dfoss/desktop/localaimodels/Assistant/DiscordBot")
    venv_python = Path("/mnt/c/users/dfoss/desktop/localaimodels/assistant/venv/bin/python")
    
    try:
        # Start bot in background
        subprocess.Popen([
            str(venv_python), "bot.py"
        ], 
        cwd=str(bot_dir),
        stdout=open(bot_dir / "bot.log", "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True  # Detach from parent
        )
        
        print("✅ Discord bot started")
        return True
        
    except Exception as e:
        print(f"❌ Error starting Discord bot: {e}")
        return False

def status():
    """Show service status"""
    print("📊 Service Status:")
    
    # Check backend (port 8000)
    backend_pids = get_processes_on_port(8000)
    if backend_pids:
        print(f"✅ Backend: Running (PIDs: {backend_pids})")
    else:
        print("❌ Backend: Not running")
    
    # Check bot processes
    try:
        result = subprocess.run(['pgrep', '-f', r'python.*bot\.py'], 
                              capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            bot_pids = result.stdout.strip().split('\n')
            print(f"✅ Discord Bot: Running (PIDs: {bot_pids})")
        else:
            print("❌ Discord Bot: Not running")
    except Exception:
        print("❌ Discord Bot: Status unknown")

def restart_all():
    """Restart all services"""
    print("🔄 Restarting all services...")
    stop_all_services()
    
    if start_backend():
        if start_bot():
            print("🎉 All services restarted successfully!")
            status()
        else:
            print("❌ Bot failed to start")
    else:
        print("❌ Backend failed to start")

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python manage_services.py stop        - Stop all services")
        print("  python manage_services.py start       - Start all services") 
        print("  python manage_services.py restart     - Restart all services")
        print("  python manage_services.py status      - Show service status")
        print("  python manage_services.py start-bot   - Start only the Discord bot")
        print("  python manage_services.py start-backend - Start only the backend")
        return
    
    command = sys.argv[1].lower()
    
    if command == "stop":
        stop_all_services()
    elif command == "start":
        if start_backend():
            start_bot()
        status()
    elif command == "restart": 
        restart_all()
    elif command == "status":
        status()
    elif command == "start-bot":
        if start_bot():
            print("✅ Discord bot started successfully")
        else:
            print("❌ Failed to start Discord bot")
    elif command == "start-backend":
        if start_backend():
            print("✅ Backend started successfully")
        else:
            print("❌ Failed to start backend")
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()