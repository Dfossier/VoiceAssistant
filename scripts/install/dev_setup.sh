#!/bin/bash
# Development Setup Script

echo '🔧 Setting up Local AI Assistant for Development...'
echo '================================================'

# Create virtual environment if it doesn't exist
if [ ! -d 'venv' ]; then
    echo '📦 Creating virtual environment...'
    python3 -m venv venv
fi

# Activate virtual environment
echo '🔧 Activating virtual environment...'
source venv/bin/activate

# Install/update dependencies
echo '📚 Installing dependencies...'
pip install -r config/requirements/requirements.txt

# Install Playwright browsers if needed
echo '🎭 Installing Playwright browsers...'
playwright install chromium

echo '✅ Development setup complete!'
echo 'Run ./scripts/launchers/quick_start.sh to start the application'
