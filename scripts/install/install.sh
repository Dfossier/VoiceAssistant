#!/bin/bash
# Local AI Assistant Installation Script for WSL

set -e

echo "🤖 Local AI Assistant - WSL Installation"
echo "========================================"

# Check if we're in WSL
if ! grep -qi microsoft /proc/version; then
    echo "⚠️  This script is designed for WSL. For Windows, see README.md"
fi

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "🐍 Python version: $python_version"

if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "❌ Python 3.11+ required. Please upgrade Python."
    exit 1
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "🔧 Upgrading pip..."
pip install --upgrade pip

# Ask user what installation they want
echo ""
echo "Choose installation type:"
echo "1) Minimal (just web chat, no AI features) - ~50MB"
echo "2) Basic (with API support, no local models) - ~200MB" 
echo "3) Full (with local model support) - ~2GB"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo "📦 Installing minimal dependencies..."
        pip install -r requirements-minimal.txt
        ;;
    2)
        echo "📦 Installing basic dependencies..."
        pip install -r requirements-wsl.txt --no-deps
        pip install fastapi uvicorn pydantic-settings python-dotenv loguru aiofiles httpx rich
        pip install langchain langchain-openai langchain-anthropic openai anthropic
        ;;
    3)
        echo "📦 Installing full dependencies (this may take 10+ minutes)..."
        pip install -r requirements-wsl.txt
        ;;
    *)
        echo "Invalid choice. Installing minimal..."
        pip install -r requirements-minimal.txt
        ;;
esac

# Setup .env if it doesn't exist with user keys
if [ ! -f ".env" ]; then
    echo "🔧 .env file not found. Let's set up your API keys..."
    cp .env .env.backup 2>/dev/null || true
    
    echo ""
    echo "Enter your API keys (press Enter to skip):"
    
    read -p "OpenAI API Key: " openai_key
    read -p "Anthropic API Key: " anthropic_key  
    read -p "Gemini API Key: " gemini_key
    
    # Update .env file
    if [ ! -z "$openai_key" ]; then
        sed -i "s/OPENAI_API_KEY=.*/OPENAI_API_KEY=$openai_key/" .env
    fi
    
    if [ ! -z "$anthropic_key" ]; then
        sed -i "s/ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=$anthropic_key/" .env
    fi
    
    if [ ! -z "$gemini_key" ]; then
        sed -i "s/GEMINI_API_KEY=.*/GEMINI_API_KEY=$gemini_key/" .env
    fi
fi

# Generate secret key
if grep -q "CHANGE_THIS_TO_A_SECURE_SECRET_KEY" .env; then
    echo "🔐 Generating secure secret key..."
    secret_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$secret_key/" .env
fi

# Create directories
echo "📁 Creating directories..."
mkdir -p logs data cache temp static/uploads

# Test installation
echo ""
echo "🧪 Testing installation..."
python3 test_basic.py

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Installation completed successfully!"
    echo ""
    echo "To start the assistant:"
    echo "  source venv/bin/activate"
    
    if [ "$choice" = "1" ]; then
        echo "  python minimal_main.py"
    else
        echo "  python main.py"
    fi
    
    echo ""
    echo "Then open your browser to: http://localhost:8000"
    echo "Or from your phone: http://$(hostname -I | awk '{print $1}'):8000"
    echo ""
    echo "Available commands once running:"
    echo "  /help    - Show help"
    echo "  /status  - System status"
    echo "  /models  - Available AI models"
    
else
    echo "❌ Installation test failed. Check the output above."
    exit 1
fi