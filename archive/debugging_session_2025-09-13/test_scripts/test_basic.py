#!/usr/bin/env python3
"""
Basic functionality test without heavy dependencies
"""
import os
import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_basic_imports():
    """Test if core modules can be imported"""
    print("🧪 Testing basic imports...")
    
    try:
        from core.config import Settings
        print("✅ Config module imported successfully")
        
        # Test configuration loading with simpler settings
        os.environ['SECRET_KEY'] = 'test_key_for_basic_test'
        os.environ['OPENAI_API_KEY'] = 'test_api_key'
        os.environ['WATCH_DIRECTORIES'] = '/tmp'
        os.environ['IGNORE_PATTERNS'] = '*.tmp'
        os.environ['ALLOWED_ORIGINS'] = 'http://localhost:8000'
        
        settings = Settings()
        print(f"✅ Settings loaded: {settings.server_host}:{settings.server_port}")
        print(f"  Watch directories: {settings.watch_directories}")
        print(f"  Ignore patterns: {settings.ignore_patterns}")
        
    except Exception as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    try:
        from utils.websocket_manager import WebSocketManager
        ws_manager = WebSocketManager()
        print("✅ WebSocket manager imported and created")
        
    except Exception as e:
        print(f"❌ WebSocket manager failed: {e}")
        return False
    
    # Test file monitoring without watchdog
    try:
        from core.file_monitor import CodeAnalyzer
        
        # Test file type detection
        test_file = Path("test.py")
        file_type = CodeAnalyzer.detect_file_type(test_file)
        print(f"✅ File analyzer works: {file_type}")
        
    except Exception as e:
        print(f"❌ File monitor failed: {e}")
        return False
    
    print("✅ All basic imports successful!")
    return True

async def test_command_executor():
    """Test command execution without heavy dependencies"""
    print("\n🧪 Testing command executor...")
    
    try:
        from core.command_executor import CommandExecutor, CommandResult
        
        # Create minimal settings
        class MinimalSettings:
            process_timeout = 30
            
        settings = MinimalSettings()
        executor = CommandExecutor(settings)
        
        # Test simple command
        result = await executor.execute_command("echo 'Hello World'")
        
        if "Hello World" in result.stdout:
            print("✅ Command execution works")
            print(f"  Output: {result.stdout.strip()}")
            print(f"  Return code: {result.return_code}")
            return True
        else:
            print(f"❌ Unexpected output: {result.stdout}")
            return False
            
    except Exception as e:
        print(f"❌ Command executor failed: {e}")
        return False

def test_directory_structure():
    """Test that required directories exist"""
    print("\n🧪 Testing directory structure...")
    
    required_dirs = [
        "src/core",
        "src/utils", 
        "static",
        "logs"
    ]
    
    all_good = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists():
            print(f"✅ {dir_path} exists")
        else:
            print(f"❌ {dir_path} missing")
            all_good = False
            
    required_files = [
        ".env",
        "requirements.txt",
        "main.py",
        "src/core/config.py",
        "src/core/server.py",
        "static/index.html"
    ]
    
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} missing")
            all_good = False
    
    return all_good

async def main():
    """Run all basic tests"""
    print("🤖 Local AI Assistant - Basic Functionality Test")
    print("=" * 50)
    
    # Test 1: Directory structure
    struct_ok = test_directory_structure()
    
    # Test 2: Basic imports
    imports_ok = await test_basic_imports()
    
    # Test 3: Command executor
    cmd_ok = await test_command_executor()
    
    print("\n" + "=" * 50)
    if struct_ok and imports_ok and cmd_ok:
        print("🎉 ALL BASIC TESTS PASSED!")
        print("The core architecture is working properly.")
        print("\nNext steps:")
        print("1. Install full dependencies: pip install -r requirements.txt")
        print("2. Run the server: python main.py")
        return True
    else:
        print("❌ Some tests failed. Check the output above.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)