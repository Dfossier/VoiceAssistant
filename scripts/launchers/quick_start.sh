#!/bin/bash
# Quick Start Script for Local AI Assistant

echo '🚀 Starting Local AI Assistant...'
echo '================================'

# Check if virtual environment exists
if [ ! -d 'venv' ]; then
    echo '❌ Virtual environment not found. Please run setup first.'
    exit 1
fi

# Activate virtual environment
echo '🔧 Activating virtual environment...'
source venv/bin/activate

# Start the main application
echo '🏁 Starting main application...'
python main.py --dev --host 0.0.0.0 --port 8000
