#!/bin/bash

echo "🚀 Starting Local AI Assistant (Simple Mode)"
echo "============================================"

# Kill any existing processes
pkill -9 -f "python3" 2>/dev/null || true

# Start the minimal server
echo "Starting backend server..."
python3 minimal_main.py > backend.log 2>&1 &
BACKEND_PID=$!

echo "Backend started with PID: $BACKEND_PID"
echo "Check http://localhost:8000 for the web interface"
echo "Check logs with: tail -f backend.log"

# Wait a bit and check if it's running
sleep 3
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is running and healthy!"
else
    echo "⚠️  Backend may still be starting..."
fi

echo ""
echo "🎉 System started! Press Ctrl+C to stop."
wait $BACKEND_PID
