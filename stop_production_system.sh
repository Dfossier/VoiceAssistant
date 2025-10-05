#!/bin/bash

echo "⏹️  Stopping Local AI Assistant Production System"
echo "================================================="

# Clean up zombie processes first  
echo "🧹 Cleaning up zombie processes..."
# Kill parent processes that might be holding zombie children
pkill -9 -f "start_production_system.sh" 2>/dev/null || true
pkill -9 -f "/bin/bash.*npm run dev" 2>/dev/null || true
# Note: Zombie processes cannot be killed directly - they're already dead
# They disappear when their parent process is reaped or killed

# Stop backend (force kill with port cleanup)
echo "🛑 Stopping backend..."
pkill -9 -f "python main.py" 2>/dev/null
lsof -ti:8000,8002 | xargs -r kill -9 2>/dev/null
if [ $? -eq 0 ] || pgrep -f "python main.py" > /dev/null; then
    echo "   ✅ Backend processes force-stopped"
else
    echo "   ℹ️  Backend was not running"
fi

# Stop web dashboard (aggressive cleanup)
echo "🛑 Stopping web dashboard..."
pkill -9 -f "npm run dev" 2>/dev/null
pkill -9 -f "vite" 2>/dev/null  
pkill -9 -f "node.*vite" 2>/dev/null
pkill -9 -f "esbuild" 2>/dev/null
pkill -9 -f "sh -c vite" 2>/dev/null
# Kill by port if processes are bound
lsof -ti:3000,3001,5173 | xargs -r kill -9 2>/dev/null
echo "   ✅ Dashboard processes force-killed"

# Stop WebSocket proxy and Discord bot (Windows processes)
echo "🛑 Stopping Discord bot and WebSocket proxy..."
# Try multiple methods to kill Python processes on Windows
echo "   🔄 Attempting to kill Windows Python processes..."

# Method 1: Kill by command line filter
taskkill.exe //F //IM python.exe //FI "COMMANDLINE eq *direct_audio_bot_working.py*" 2>/dev/null && echo "   ✓ Killed Discord bot via command line filter" || echo "   ℹ️  No Discord bot processes found"
taskkill.exe //F //IM python.exe //FI "COMMANDLINE eq *websocket_proxy.py*" 2>/dev/null && echo "   ✓ Killed WebSocket proxy via command line filter" || echo "   ℹ️  No proxy processes found"

# Method 2: Kill ALL Python processes on Windows (aggressive)
powershell.exe -Command "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null && echo "   ✓ Killed all Windows Python processes" || echo "   ℹ️  No Python processes found"

# Method 3: Kill any WSL processes
pkill -9 -f "direct_audio_bot_working.py" 2>/dev/null && echo "   ✓ Killed WSL Discord processes" || echo "   ℹ️  No WSL Discord processes found"
pkill -9 -f "websocket_proxy.py" 2>/dev/null && echo "   ✓ Killed WSL proxy processes" || echo "   ℹ️  No WSL proxy processes found"

# Wait for processes to fully terminate
sleep 3
echo "   ✅ Discord bot shutdown attempted (check Discord to verify bot disconnected)"

# Check for any remaining processes
echo ""
echo "📊 Checking for remaining processes..."
BACKEND_REMAINING=$(ps aux | grep "python main.py" | grep -v grep)
DASHBOARD_REMAINING=$(ps aux | grep -E "(npm run dev|vite)" | grep -v grep)
BOT_REMAINING=$(tasklist.exe //FI "IMAGENAME eq python.exe" 2>/dev/null | grep -i python || echo "")

if [ -z "$BACKEND_REMAINING" ] && [ -z "$DASHBOARD_REMAINING" ] && [ -z "$BOT_REMAINING" ]; then
    echo "   ✅ All services stopped successfully"
else
    echo "   ⚠️  Some processes may still be running:"
    if [ ! -z "$BACKEND_REMAINING" ]; then
        echo "   Backend: $BACKEND_REMAINING"
    fi
    if [ ! -z "$DASHBOARD_REMAINING" ]; then
        echo "   Dashboard: $DASHBOARD_REMAINING"
    fi
    if [ ! -z "$BOT_REMAINING" ]; then
        echo "   Discord: $BOT_REMAINING"
    fi
fi

echo ""
echo "✅ Production system shutdown complete"