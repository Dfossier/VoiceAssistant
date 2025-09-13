#!/usr/bin/env python3
"""Local AI Assistant startup script"""
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Check if we're in a virtual environment
in_venv = sys.prefix != sys.base_prefix

print("🤖 Local AI Assistant")
print("=" * 40)
print(f"Python: {sys.version}")
print(f"Virtual Environment: {'Yes' if in_venv else 'No'}")
print(f"Project Directory: {project_root}")

# Check voice support
try:
    import pyttsx3
    print("🎤 Voice TTS: Available")
except ImportError:
    print("🎤 Voice TTS: Not available (install pyttsx3)")

print()

# Check for configuration
env_file = project_root / ".env"
if env_file.exists():
    print("✅ Configuration found (.env)")
else:
    print("⚠️  No .env file found. Copy .env.example to .env and configure your API keys.")
    sys.exit(1)

# Import and run the server
try:
    from src.core.config import Settings
    from src.core.server import create_app, run_server
    
    print("🚀 Starting Local AI Assistant server...")
    print("📱 Access from:")
    print("   - Desktop: http://localhost:8000")
    print("   - Phone (same network): http://[your-pc-ip]:8000")
    print()
    print("🎤 Voice Chat: Click the Voice button in the web interface")
    print("📝 Commands: Type /help for available commands")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 40)
    
    # Load settings and create app
    settings = Settings()
    app = create_app(settings)
    
    # Run the server
    run_server(app, settings)
    
except KeyboardInterrupt:
    print("\n👋 Goodbye!")
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nTroubleshooting:")
    print("1. Ensure all dependencies are installed: pip install -r requirements.txt")
    print("2. Check your .env configuration")
    print("3. Verify Python path and imports")
    sys.exit(1)