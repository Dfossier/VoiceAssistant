#!/bin/bash

echo "🚀 Starting Local AI Assistant System"
echo "===================================="

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Please run this script from the assistant directory"
    exit 1
fi

# Kill any existing processes
echo "🔄 Cleaning up existing processes..."
pkill -f "python main.py" 2>/dev/null
pkill -f "npm run dev" 2>/dev/null
sleep 2

# Start backend
echo ""
echo "1️⃣ Starting Backend API..."
source venv/bin/activate 2>/dev/null || {
    echo "❌ Error: Virtual environment not found. Please create it first."
    exit 1
}

# Start backend in background
python main.py > backend.log 2>&1 &
BACKEND_PID=$!
echo "   ✅ Backend started (PID: $BACKEND_PID)"

# Wait for backend to be ready
echo "   ⏳ Waiting for backend to initialize..."
sleep 5

# Check if backend is running
if kill -0 $BACKEND_PID 2>/dev/null; then
    echo "   ✅ Backend is running"
    
    # Test API endpoint
    if curl -s http://localhost:8000/api/system/status > /dev/null 2>&1; then
        echo "   ✅ API endpoints are accessible!"
    else
        echo "   ⚠️  API endpoints may not be fully ready yet"
    fi
else
    echo "   ❌ Backend failed to start. Check backend.log"
    exit 1
fi

# Start web dashboard
echo ""
echo "2️⃣ Starting Web Dashboard..."
cd web-dashboard
npm run dev > ../dashboard.log 2>&1 &
DASHBOARD_PID=$!
cd ..
echo "   ✅ Dashboard started (PID: $DASHBOARD_PID)"

# Show status
echo ""
echo "✅ System Started Successfully!"
echo "==============================="
echo ""
echo "🌐 Web Dashboard: http://localhost:3001"
echo "🔧 Backend API:   http://localhost:8000"
echo "🎤 Voice Pipeline: ws://localhost:8002"
echo ""
echo "📊 Service Status:"
echo "   • Backend:    Running (PID: $BACKEND_PID)"
echo "   • Dashboard:  Running (PID: $DASHBOARD_PID)"
echo ""
echo "📝 Logs:"
echo "   • Backend:    tail -f backend.log"
echo "   • Dashboard:  tail -f dashboard.log"
echo ""
echo "⏹️  To stop all services: ./stop_system.sh"
echo ""
echo "Press Ctrl+C to stop watching (services will continue running)"

# Keep script running to show any errors
tail -f backend.log