#!/bin/bash

# Simple Backend Startup Script
echo "🚀 Starting Backend Only"

# Kill any existing backend
pkill -f "python main.py" 2>/dev/null || true
sleep 2

# Start backend
source venv/bin/activate
nohup python main.py > backend.log 2>&1 &
BACKEND_PID=$!

echo "✅ Backend started with PID: $BACKEND_PID"
echo "⏳ Waiting for models to load..."

# Wait for backend to be ready
for i in {1..60}; do
    if curl -s http://localhost:8000/health | grep -q "healthy"; then
        echo "✅ Backend is ready!"
        echo "📍 Backend: http://localhost:8000"
        echo "📍 Health: http://localhost:8000/health"
        echo "📍 Voice: ws://localhost:8002"
        exit 0
    fi
    sleep 3
done

echo "❌ Backend failed to start properly"
exit 1