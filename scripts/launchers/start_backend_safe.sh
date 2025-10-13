#!/bin/bash
# Safe backend startup script that clears port conflicts

echo "🚀 Starting backend with port conflict resolution..."

# Check and clear port 8002
echo "🔍 Checking port 8002..."
python3 fix_port_conflict.py 8002

# Activate virtual environment
echo "🐍 Activating virtual environment..."
source venv/bin/activate

# Start the simple audio handler on port 8002
echo "🎵 Starting SimpleAudioWebSocketHandler on port 8002..."
python start_simple_handler.py

# Note: The script will keep running as long as the server is running
# Press Ctrl+C to stop the server