#!/bin/bash

set -e  # Exit on any error

echo "🚀 Starting Local AI Assistant Production System"
echo "================================================"

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Please run this script from the assistant directory containing main.py"
    exit 1
fi

# Aggressive cleanup of existing processes
echo "🔄 Cleaning up existing processes..."
pkill -9 -f "python3 main.py" 2>/dev/null || true
pkill -9 -f "direct_audio_bot_working.py" 2>/dev/null || true
pkill -9 -f "npm run dev" 2>/dev/null || true
pkill -9 -f "vite" 2>/dev/null || true
pkill -9 -f "node.*vite" 2>/dev/null || true
pkill -9 -f "esbuild" 2>/dev/null || true
pkill -9 -f "sh -c vite" 2>/dev/null || true
# Kill any processes on relevant ports
lsof -ti:8000,8002,3000,5173 | xargs -r kill -9 2>/dev/null || true
sleep 3

# Activate virtual environment for CUDA support
if [ -d "venv" ]; then
    echo "🔥 Activating virtual environment for CUDA acceleration..."
    source venv/bin/activate
    python3 -c "import torch; print(f'🚀 CUDA Available: {torch.cuda.is_available()}'); print(f'💻 GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU Only\"}')" 2>/dev/null || echo "⚠️ PyTorch not available for CUDA check"
    echo "   ✅ Virtual environment activated"
else
    echo "⚠️ No virtual environment found - using system Python"
fi

# Start backend server
echo "1️⃣ Starting Backend Server..."
python3 main.py > minimal_server.log 2>&1 &
BACKEND_PID=$!
echo "   ✅ Backend started (PID: $BACKEND_PID)"

# Wait for backend to fully start (up to 60 seconds)
echo "   ⏳ Waiting for backend to initialize..."
for i in {1..60}; do
    if tail -20 minimal_server.log 2>/dev/null | grep -q "Application startup complete"; then
        echo "   ✅ Backend startup complete"
        sleep 2  # Brief pause for stability
        break
    fi

    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "   ❌ Backend process crashed during startup"
        echo "   📝 Check minimal_server.log for details:"
        tail -20 minimal_server.log
        exit 1
    fi

    if [ $((i % 10)) -eq 0 ]; then
        echo "   ⏳ Still initializing... (${i}s elapsed)"
    fi
    sleep 1
done

# Verify backend is still running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "   ❌ Backend failed to start within timeout"
    exit 1
fi

echo "   ✅ Backend is running and accessible"

# Start WebSocket Handler for voice processing
echo ""
echo "1.5️⃣ Starting Enhanced WebSocket Handler (Voice Pipeline)..."
python3 start_websocket_service.py > websocket_service.log 2>&1 &
WEBSOCKET_PID=$!
echo "   ✅ WebSocket Handler started (PID: $WEBSOCKET_PID)"
sleep 2

# Start web dashboard
echo ""
echo "2️⃣ Starting Web Dashboard..."
cd web-dashboard
npm run dev > ../dashboard.log 2>&1 &
DASHBOARD_PID=$!
cd ..
echo "   ✅ Dashboard started (PID: $DASHBOARD_PID)"

# Test MCP server (optional)
echo ""
echo "2.5️⃣ Testing MCP Server..."
if timeout 5 python3 mcp-terminal-server/terminal_server.py < /dev/null >/dev/null 2>&1; then
    echo "   ✅ MCP server test passed"
else
    echo "   ⚠️  MCP server test failed (this is normal for stdio servers)"
fi

# Start Discord bot (Windows)
echo ""
echo "3️⃣ Starting Discord Bot (Windows) - System Audio Mode..."
if [ -f "WindowsDiscordBot/direct_audio_bot_working.py" ]; then
    echo "   🌉 Starting WebSocket proxy on Windows (port 8003)..."
    cd WindowsDiscordBot
    # Start proxy in background
    cmd.exe /c "bot_venv_windows\\Scripts\\python websocket_proxy.py > proxy_windows.log 2>&1" &
    sleep 3
    echo "   📱 Starting Discord bot..."
    # Start bot in background 
    cmd.exe /c "bot_venv_windows\\Scripts\\python direct_audio_bot_working.py > discord_bot_windows.log 2>&1" &
    cd ..
    sleep 2
    echo "   ✅ Discord bot and proxy startup commands issued"
else
    echo "   ❌ Discord bot file not found: WindowsDiscordBot/direct_audio_bot_working.py"
fi

# Final status display
echo ""
echo "✅ Production System Started Successfully!"
echo "========================================="
echo ""
echo "🌐 Web Dashboard: http://localhost:3000"
echo "🔧 Backend API:   http://127.0.0.1:8000"
echo "🎤 Voice Pipeline: ws://10.2.0.2:8002"
echo ""
echo "📊 System Status:"
echo "   • Backend:    Running (PID: $BACKEND_PID)"
echo "   • WebSocket:  Running (PID: $WEBSOCKET_PID)"
echo "   • Dashboard:  Running (PID: $DASHBOARD_PID)"
echo "   • Discord Bot: Background process (check Discord for online status)"
echo ""
echo "📝 Logs:"
echo "   • Backend:    tail -f minimal_server.log"
echo "   • WebSocket:  tail -f websocket_service.log"
echo "   • Dashboard:  tail -f dashboard.log"
echo ""
echo "🎮 Discord Usage:"
echo "   1. Join a voice channel in Discord"
echo "   2. Type: !direct (starts system audio capture)"
echo "   3. Type: !stop (ends capture and disconnects)"
echo ""
echo "⏹️  To stop all services: ./scripts/stop_production_system.sh"
