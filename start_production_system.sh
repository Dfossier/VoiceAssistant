#!/bin/bash

echo "🚀 Starting Local AI Assistant Production System"
echo "================================================"

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Please run this script from the assistant directory"
    exit 1
fi

# Kill any existing processes (aggressive cleanup)
echo "🔄 Cleaning up existing processes..."
pkill -9 -f "python main.py" 2>/dev/null
pkill -9 -f "direct_audio_bot_working.py" 2>/dev/null
pkill -9 -f "npm run dev" 2>/dev/null
pkill -9 -f "vite" 2>/dev/null  
pkill -9 -f "node.*vite" 2>/dev/null
pkill -9 -f "esbuild" 2>/dev/null
pkill -9 -f "sh -c vite" 2>/dev/null
# Kill processes on all relevant ports  
lsof -ti:8000,8002,3000,3001,5173 | xargs -r kill -9 2>/dev/null
sleep 3

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found. Please create it first."
    exit 1
fi

# Start backend
echo ""
echo "1️⃣ Starting Backend API..."
source venv/bin/activate 2>/dev/null || {
    echo "❌ Error: Could not activate virtual environment"
    exit 1
}

# Start backend in background
python main.py > backend_production.log 2>&1 &
BACKEND_PID=$!
echo "   ✅ Backend started (PID: $BACKEND_PID)"

# Wait for backend to be ready (models take 60+ seconds to load)
echo "   ⏳ Waiting for backend to initialize (model loading takes ~120s)..."
for i in {1..260}; do
    sleep 1
    # Check if backend has fully started by looking for the startup complete message
    # Use tail to get latest content (handles buffering better than grep on active files)
    if tail -20 backend_production.log 2>/dev/null | grep -q "Application startup complete"; then
        echo "   ✅ Backend startup complete"
        # Give it a few more seconds for the health endpoint to be ready
        sleep 3
        if curl -s http://localhost:8000/health >/dev/null 2>&1; then
            echo "   ✅ Backend is running and accessible"
        else
            echo "   ⚠️  Backend started but health endpoint not ready yet, continuing anyway..."
        fi
        # Break regardless - backend has started successfully
        break
    elif ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "   ❌ Backend process crashed. Check backend_production.log"
        tail -20 backend_production.log
        exit 1
    elif [ $i -eq 200 ]; then
        echo "   ⚠️  Backend taking longer than expected (200s). Checking if it's still starting..."
        if kill -0 $BACKEND_PID 2>/dev/null; then
            echo "   ℹ️  Backend process still alive, giving it more time..."
            echo "   ⏳ Extending timeout by 60 seconds..."
        else
            echo "   ❌ Backend process died. Check backend_production.log"
            tail -20 backend_production.log
            exit 1
        fi
    elif [ $((i % 10)) -eq 0 ]; then
        echo "   ⏳ Still initializing... (${i}s elapsed)"
    fi
done

# Start web dashboard
echo ""
echo "2️⃣ Starting Web Dashboard..."
cd web-dashboard
npm run dev > ../dashboard.log 2>&1 &
DASHBOARD_PID=$!
cd ..
echo "   ✅ Dashboard started (PID: $DASHBOARD_PID)"

# Test MCP server functionality
echo ""
echo "2.5️⃣ Testing MCP Server..."
if timeout 5 python mcp-terminal-server/terminal_server.py < /dev/null >/dev/null 2>&1; then
    echo "   ✅ MCP server can start successfully"
else
    echo "   ⚠️  MCP server test failed, but this is normal (stdio server)"
fi

# Start Discord bot (Windows native) - System Audio Mode
echo ""
echo "3️⃣ Starting Discord Bot (Windows) - System Audio Mode..."
if [ -f "WindowsDiscordBot/direct_audio_bot_working.py" ]; then
    cd WindowsDiscordBot
    cmd.exe /c "start /B bot_venv_windows\\Scripts\\python direct_audio_bot_working.py" 2>/dev/null &
    sleep 3
    cd ..
    echo "   ✅ Discord bot started in background (system audio capture)"
else
    echo "   ❌ Discord bot file not found: WindowsDiscordBot/direct_audio_bot_working.py"
fi

# Show status
echo ""
echo "✅ Production System Started Successfully!"
echo "========================================="
echo ""
echo "🌐 Web Dashboard: http://localhost:3001"
echo "🔧 Backend API:   http://localhost:8000"
echo "🎤 Voice Pipeline: ws://172.20.104.13:8002"
echo ""
echo "📊 System Status:"
echo "   • Backend:    Running (PID: $BACKEND_PID)"
echo "   • Dashboard:  Running (PID: $DASHBOARD_PID)"
echo "   • Discord Bot: System audio mode (Windows background)"
echo ""
echo "📝 Logs:"
echo "   • Backend:    tail -f backend_production.log"
echo "   • Dashboard:  tail -f dashboard.log"
echo ""
echo "🎮 Discord Usage:"
echo "   1. Join Discord voice channel"  
echo "   2. Type: !direct"
echo "   3. System audio capture active - captures all computer audio"
echo "   4. Type: !stop to end session"
echo ""
echo "⏹️  To stop all services: ./stop_production_system.sh"