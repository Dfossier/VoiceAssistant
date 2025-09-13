#!/usr/bin/env python3
"""
Local AI Assistant Setup Script
Run this after installing requirements.txt
"""
import os
import sys
import secrets
import subprocess
from pathlib import Path


def main():
    """Main setup function"""
    print("🤖 Local AI Assistant Setup")
    print("=" * 40)
    
    # Check if .env exists
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ .env file not found!")
        print("Please copy the .env file and configure your API keys first.")
        return False
    
    # Generate secure secret key if needed
    setup_secret_key()
    
    # Create directories
    create_directories()
    
    # Install Playwright browsers
    install_playwright()
    
    # Validate configuration
    validate_config()
    
    print("\n✅ Setup completed successfully!")
    print("Run 'python main.py' to start the assistant")
    return True


def setup_secret_key():
    """Generate and set a secure secret key"""
    print("\n🔐 Checking secret key...")
    
    # Read current .env
    with open(".env", "r") as f:
        content = f.read()
    
    # Check if default key is still in use
    if "CHANGE_THIS_TO_A_SECURE_SECRET_KEY" in content:
        print("Generating secure secret key...")
        new_key = secrets.token_urlsafe(32)
        content = content.replace(
            "SECRET_KEY=CHANGE_THIS_TO_A_SECURE_SECRET_KEY",
            f"SECRET_KEY={new_key}"
        )
        
        with open(".env", "w") as f:
            f.write(content)
        print("✅ Secret key generated")
    else:
        print("✅ Secret key already configured")


def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating directories...")
    
    directories = [
        "logs",
        "data",
        "cache", 
        "temp",
        "static/uploads"
    ]
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print(f"  Created: {directory}")
    
    print("✅ Directories created")


def install_playwright():
    """Install Playwright browsers"""
    print("\n🎭 Installing Playwright browsers...")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Playwright browsers installed")
        else:
            print("❌ Failed to install Playwright browsers")
            print(result.stderr)
            
    except Exception as e:
        print(f"❌ Error installing Playwright: {e}")


def validate_config():
    """Validate the configuration"""
    print("\n✅ Validating configuration...")
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check for at least one API key
    has_api_key = any([
        os.getenv("OPENAI_API_KEY"),
        os.getenv("ANTHROPIC_API_KEY"),
        os.getenv("GEMINI_API_KEY")
    ])
    
    if has_api_key:
        print("✅ At least one LLM API key configured")
    else:
        print("⚠️  No LLM API keys found - please add to .env file")
    
    # Check secret key
    secret_key = os.getenv("SECRET_KEY")
    if secret_key and secret_key != "CHANGE_THIS_TO_A_SECURE_SECRET_KEY":
        print("✅ Secret key configured")
    else:
        print("❌ Please set SECRET_KEY in .env file")


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)