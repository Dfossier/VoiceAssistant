#!/bin/bash

echo "🔧 Setting up Local AI Assistant for Development..."
echo "=================================================="

# Check Python version
python3 --version

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo "📚 Installing Python dependencies..."
pip install -r config/requirements/requirements.txt

# Install Playwright browsers
echo "🎭 Installing Playwright browsers..."
playwright install chromium

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Please create one with your API keys:"
    echo "   OPENAI_API_KEY=your_key_here"
    echo "   ANTHROPIC_API_KEY=your_key_here"
    echo "   GEMINI_API_KEY=your_key_here"
    echo "   SECRET_KEY=your_secure_secret_key_here"
fi

echo "✅ Development setup complete!"
echo ""
echo "🚀 To start the application:"
echo "   source venv/bin/activate"
echo "   python main.py --dev"
