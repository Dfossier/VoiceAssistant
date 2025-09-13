#!/usr/bin/env python3
"""
Quick Start Script for Local AI Assistant
Installs minimal dependencies and runs a basic version
"""
import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and show progress"""
    print(f"📦 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False

def main():
    print("🚀 Local AI Assistant - Quick Start")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not Path("main.py").exists():
        print("❌ Please run this from the assistant directory")
        return False
    
    # Create virtual environment if it doesn't exist
    if not Path("venv").exists():
        print("🔧 Creating virtual environment...")
        if not run_command("python3 -m venv venv", "Virtual environment creation"):
            return False
    
    # Install minimal dependencies for quick start
    minimal_deps = [
        "fastapi",
        "uvicorn[standard]", 
        "pydantic-settings",
        "python-dotenv",
        "loguru",
        "aiofiles",
        "httpx"
    ]
    
    deps_str = " ".join(minimal_deps)
    if not run_command(f"source venv/bin/activate && pip install {deps_str}", "Installing minimal dependencies"):
        return False
    
    # Check .env file
    if not Path(".env").exists():
        print("❌ .env file not found. Please configure your API keys first.")
        return False
        
    # Test basic functionality
    print("\n🧪 Testing basic functionality...")
    if run_command("source venv/bin/activate && python test_basic.py", "Basic functionality test"):
        print("\n🎉 Quick start successful!")
        print("\nNext steps:")
        print("1. Configure your API keys in .env file")
        print("2. Run: source venv/bin/activate && python main.py")
        print("3. Open browser: http://localhost:8000")
        print("4. For full features, install: pip install -r requirements.txt")
        return True
    else:
        print("❌ Basic tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)