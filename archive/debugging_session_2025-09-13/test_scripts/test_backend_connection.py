"""Test connection from Windows to WSL2 backend"""
import requests
import json

# Backend API URL - accessible from Windows to WSL2
BACKEND_URL = "http://127.0.0.1:8000"
API_KEY = "your-secure-api-key-here-change-this"

def test_connection():
    try:
        # Test basic connection
        response = requests.get(f"{BACKEND_URL}/")
        print(f"✅ Backend reachable: {response.status_code}")
        
        # Test API endpoint
        headers = {"X-API-Key": API_KEY}
        response = requests.get(f"{BACKEND_URL}/api/health", headers=headers)
        
        if response.status_code == 200:
            print(f"✅ API health check: {response.json()}")
        else:
            print(f"❌ API health check failed: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend API!")
        print("Make sure the backend is running in WSL2 on port 8000")
        print("You may need to check Windows Firewall settings")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Testing connection to WSL2 backend API...")
    test_connection()