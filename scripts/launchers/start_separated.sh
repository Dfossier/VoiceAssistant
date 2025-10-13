#!/bin/bash
# Start services separately for better control and no blocking

echo "🚀 Starting Local AI Assistant (Separated Mode)"
echo "=============================================="

# Kill any existing processes
echo "🧹 Cleaning up existing processes..."
pkill -f "run_api_only.py" 2>/dev/null
pkill -f "run_voice_only.py" 2>/dev/null
pkill -f "python.*test_api" 2>/dev/null
pkill -f "uvicorn" 2>/dev/null
sleep 2

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    exit 1
fi

# Start API server
echo ""
echo "1️⃣ Starting API Server (port 8000)..."
source venv/bin/activate
python run_api_only.py > api_server.log 2>&1 &
API_PID=$!
echo "   ✅ API Server started (PID: $API_PID)"

# Wait for API to be ready
echo "   ⏳ Waiting for API to initialize..."
for i in {1..10}; do
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo "   ✅ API is ready!"
        break
    fi
    sleep 1
done

# Start Voice Pipeline
echo ""
echo "2️⃣ Starting Voice Pipeline (port 8002)..."
python run_voice_only.py > voice_pipeline.log 2>&1 &
VOICE_PID=$!
echo "   ✅ Voice Pipeline started (PID: $VOICE_PID)"

# Start Dashboard (optional)
echo ""
echo "3️⃣ Starting Web Dashboard (port 3000)..."
cd web-dashboard
npm run dev > ../dashboard.log 2>&1 &
DASH_PID=$!
cd ..
echo "   ✅ Dashboard started (PID: $DASH_PID)"

# Summary
echo ""
echo "✅ System Started Successfully!"
echo "==============================="
echo ""
echo "📊 Service Status:"
echo "   • API Server:     http://localhost:8000 (PID: $API_PID)"
echo "   • Voice Pipeline: ws://localhost:8002 (PID: $VOICE_PID)"
echo "   • Dashboard:      http://localhost:3000 (PID: $DASH_PID)"
echo ""
echo "📝 Logs:"
echo "   • API:    tail -f api_server.log"
echo "   • Voice:  tail -f voice_pipeline.log"  
echo "   • Dash:   tail -f dashboard.log"
echo ""
echo "🛑 To stop all: ./shutdown_all.sh"
echo ""
echo "🎤 Discord Bot Connection:"
echo "   The bot should connect to: ws://localhost:8002"