#!/usr/bin/env python3
"""
Test script for Discord AI Assistant Backend API
"""
import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import httpx
from loguru import logger

# Configuration
BASE_URL = "http://localhost:8080"
API_KEY = "your-secure-api-key-here-change-this"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

async def test_health():
    """Test health endpoint"""
    print("🏥 Testing health endpoint...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
            assert response.status_code == 200
        print("✅ Health check passed!\n")
    except Exception as e:
        print(f"❌ Health check failed: {e}\n")

async def test_conversation():
    """Test conversation endpoint"""
    print("💬 Testing conversation endpoint...")
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "user_id": "test_user_123",
                "message": "Hello! Can you help me debug a Python error?",
                "context": {
                    "current_directory": "/test/project",
                    "active_files": ["main.py", "utils.py"]
                }
            }
            
            response = await client.post(
                f"{BASE_URL}/api/conversation/message",
                json=payload,
                headers=HEADERS,
                timeout=30
            )
            
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Response: {data['response'][:100]}...")
                print(f"Suggestions: {data['suggestions']}")
                print(f"Files referenced: {data['files_referenced']}")
            else:
                print(f"Error: {response.text}")
        print("✅ Conversation test passed!\n")
    except Exception as e:
        print(f"❌ Conversation test failed: {e}\n")

async def test_file_operations():
    """Test file operations"""
    print("📁 Testing file operations...")
    try:
        # Test reading current file
        current_file = str(Path(__file__).absolute())
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/files/content",
                params={"path": current_file, "lines": "1-10"},
                headers=HEADERS
            )
            
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"File path: {data['path']}")
                print(f"Content preview: {data['content'][:50]}...")
                print(f"Lines: {data['lines']}")
            else:
                print(f"Error: {response.text}")
        print("✅ File operations test passed!\n")
    except Exception as e:
        print(f"❌ File operations test failed: {e}\n")

async def test_command_execution():
    """Test command execution"""
    print("⚡ Testing command execution...")
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "user_id": "test_user_123",
                "command": "echo 'Hello from command execution!'",
                "timeout": 10
            }
            
            response = await client.post(
                f"{BASE_URL}/api/exec/command",
                json=payload,
                headers=HEADERS
            )
            
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                job_id = data["job_id"]
                print(f"Job ID: {job_id}")
                
                # Wait a moment and check status
                await asyncio.sleep(2)
                
                status_response = await client.get(
                    f"{BASE_URL}/api/exec/status/{job_id}",
                    headers=HEADERS
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"Command status: {status_data['status']}")
                    
                    # Get output
                    output_response = await client.get(
                        f"{BASE_URL}/api/exec/output/{job_id}",
                        headers=HEADERS
                    )
                    
                    if output_response.status_code == 200:
                        output_data = output_response.json()
                        print(f"Stdout: {output_data['stdout']}")
                        print(f"Return code: {output_data['return_code']}")
            else:
                print(f"Error: {response.text}")
        print("✅ Command execution test passed!\n")
    except Exception as e:
        print(f"❌ Command execution test failed: {e}\n")

async def test_project_analysis():
    """Test project analysis"""
    print("🔍 Testing project analysis...")
    try:
        async with httpx.AsyncClient() as client:
            current_dir = str(Path(__file__).parent)
            
            response = await client.get(
                f"{BASE_URL}/api/project/structure",
                params={"path": current_dir, "max_depth": 2},
                headers=HEADERS
            )
            
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Project path: {data['path']}")
                print(f"Structure keys: {list(data['structure']['tree'].keys())[:5]}...")
            else:
                print(f"Error: {response.text}")
        print("✅ Project analysis test passed!\n")
    except Exception as e:
        print(f"❌ Project analysis test failed: {e}\n")

async def main():
    """Run all tests"""
    print("🧪 Discord AI Assistant Backend API Tests")
    print("=" * 50)
    print(f"Base URL: {BASE_URL}")
    print(f"API Key: {API_KEY[:10]}...")
    print()
    
    # Run tests
    await test_health()
    await test_conversation()
    await test_file_operations()
    await test_command_execution()
    await test_project_analysis()
    
    print("🎉 All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())