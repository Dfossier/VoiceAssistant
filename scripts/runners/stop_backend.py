#!/usr/bin/env python3
"""
Emergency backend stopper
Directly kills the backend process by checking running processes
"""
import subprocess
import sys
import time
import requests

def check_backend_running():
    """Check if backend is running"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def stop_backend():
    """Stop the backend process"""
    print("Stopping backend processes...")
    
    # Try graceful shutdown first
    if check_backend_running():
        print("Backend is running, attempting to stop...")
        
        # Kill via WSL if available
        try:
            result = subprocess.run(
                ["bash", "-c", "pkill -f 'python3.*main.py'"],
                capture_output=True,
                text=True,
                timeout=10
            )
            print(f"WSL kill result: {result.returncode}")
        except Exception as e:
            print(f"WSL kill failed: {e}")
        
        # Wait and check
        time.sleep(3)
        
        if check_backend_running():
            print("Backend still running, trying more aggressive approach...")
            try:
                # Try with python subprocess module
                result = subprocess.run(
                    ["bash", "-c", "pkill -9 python3"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                print(f"Aggressive kill result: {result.returncode}")
            except Exception as e:
                print(f"Aggressive kill failed: {e}")
        
        # Final check
        time.sleep(2)
        if not check_backend_running():
            print("✅ Backend stopped successfully")
        else:
            print("❌ Backend still running - manual intervention required")
            print("Please manually stop the python3 main.py process")
    else:
        print("✅ Backend is not running")

if __name__ == "__main__":
    stop_backend()