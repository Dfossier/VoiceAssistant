#!/bin/bash
# Simple run script for Local AI Assistant

cd "$(dirname "$0")"

echo "🤖 Starting Local AI Assistant"
echo "=============================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./install.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check which version to run
if command -v transformers &> /dev/null && python -c "import langchain" &> /dev/null 2>&1; then
    echo "🚀 Starting full version..."
    python main.py "$@"
elif python -c "import langchain" &> /dev/null 2>&1; then
    echo "🚀 Starting basic version..."  
    python main.py "$@"
else
    echo "🚀 Starting minimal version..."
    python minimal_main.py "$@"
fi