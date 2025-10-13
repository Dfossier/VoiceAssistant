#!/usr/bin/env python3
"""
Direct kill for the backend process
Uses different approaches to stop the stubborn backend
"""
import subprocess
import requests
import time
import sys
import os

def check_backend():
    try:
        r = requests.get("http://localhost:8000/health", timeout=2)
        return r.status_code == 200
    except:
        return False

def method1_wsl_direct():
    """Method 1: WSL direct command"""
    print("Method 1: WSL direct pkill...")
    try:
        # Try different WSL command formats
        commands = [
            ["wsl", "pkill", "-f", "python3.*main.py"],
            ["wsl", "pkill", "-9", "python3"],
            ["wsl", "bash", "-c", "pkill -f 'python3.*main.py'"],
            ["wsl", "--exec", "pkill", "-f", "main.py"]
        ]
        
        for cmd in commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                print(f"Command {' '.join(cmd)}: exit={result.returncode}")
                if result.returncode == 0:
                    print("Success with this command!")
                    return True
            except Exception as e:
                print(f"Failed: {e}")
        
        return False
    except Exception as e:
        print(f"Method 1 failed: {e}")
        return False

def method2_subprocess():
    """Method 2: Use subprocess with shell=True"""
    print("Method 2: Shell=True approach...")
    try:
        commands = [
            "wsl pkill -f 'python3.*main.py'",
            "wsl pkill -9 python3",
            "bash -c 'pkill -f python3'",
        ]
        
        for cmd in commands:
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                print(f"Command '{cmd}': exit={result.returncode}")
                if result.returncode in [0, 1]:  # 0=success, 1=no process found
                    print("Process killed or not found")
                    return True
            except Exception as e:
                print(f"Failed: {e}")
        
        return False
    except Exception as e:
        print(f"Method 2 failed: {e}")
        return False

def main():
    print("=== Direct Backend Kill Tool ===")
    print()
    
    if not check_backend():
        print("✅ Backend is not running")
        return
    
    print("❌ Backend is running (old code), attempting to stop...")
    print()
    
    # Try different methods
    if method1_wsl_direct():
        time.sleep(2)
        if not check_backend():
            print("✅ Backend stopped successfully!")
            return
    
    if method2_subprocess():
        time.sleep(2)  
        if not check_backend():
            print("✅ Backend stopped successfully!")
            return
    
    print()
    print("❌ All methods failed. Manual intervention required:")
    print("1. Find the WSL terminal running 'python3 main.py'")
    print("2. Press Ctrl+C to stop it")
    print("3. Or use Task Manager to kill WSL processes")

if __name__ == "__main__":
    main()