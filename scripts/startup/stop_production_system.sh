#!/bin/bash

echo "⏹️  Stopping Local AI Assistant Production System"
echo "================================================="

# Nuclear option for Discord bot - kill ALL Python processes on Windows first
echo "🔥 AGGRESSIVE: Killing ALL Python processes on Windows..."
powershell.exe -Command "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null && echo "   ✓ Killed all Windows Python" || echo "   ℹ️  No Windows Python found"

# Kill all cmd.exe processes that might be running Python
echo "🔥 Killing suspicious cmd.exe processes..."
taskkill.exe //F //IM cmd.exe //FI "COMMANDLINE eq *python*" 2>/dev/null && echo "   ✓ Killed Python-related cmd.exe" || echo "   ℹ️  No Python cmd.exe found"

# Kill WSL wrapper processes (more aggressive)
echo "🔥 Killing WSL wrapper processes..."
pkill -9 -f "/init" 2>/dev/null && echo "   ✓ Killed WSL init processes" || echo "   ℹ️  No WSL init found"
pkill -9 -f "cmd.exe" 2>/dev/null && echo "   ✓ Killed WSL cmd processes" || echo "   ℹ️  No WSL cmd found"

# Kill any discord/bot related processes
echo "🔥 Killing Discord-related processes..."
pkill -9 -f "discord" 2>/dev/null && echo "   ✓ Killed Discord processes" || echo "   ℹ️  No Discord processes found"
pkill -9 -f "bot" 2>/dev/null && echo "   ✓ Killed bot processes" || echo "   ℹ️  No bot processes found"

# Clean up parent processes
echo "🧹 Cleaning up parent processes..."
pkill -9 -f "start_production_system.sh" 2>/dev/null || true
pkill -9 -f "/bin/bash.*npm run dev" 2>/dev/null || true

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
# Kill npm processes first
pkill -9 -f "npm run dev" 2>/dev/null && echo "   ✓ Killed npm processes"
# Kill shell wrappers
pkill -9 -f "sh -c vite" 2>/dev/null && echo "   ✓ Killed shell wrappers"
# Kill vite processes
pkill -9 -f "vite" 2>/dev/null && echo "   ✓ Killed vite processes"
# Kill node processes running vite
pkill -9 -f "node.*vite" 2>/dev/null && echo "   ✓ Killed node vite processes"
# Kill esbuild processes
pkill -9 -f "esbuild" 2>/dev/null && echo "   ✓ Killed esbuild processes"
# Kill any remaining processes by port
lsof -ti:3000,3001,5173 | xargs -r kill -9 2>/dev/null && echo "   ✓ Killed port-bound processes"
# Additional cleanup - kill any process tree from the dashboard directory
ps aux | grep -E "web-dashboard.*node" | grep -v grep | awk '{print $2}' | xargs -r kill -9 2>/dev/null && echo "   ✓ Killed remaining dashboard processes"
echo "   ✅ Dashboard processes force-killed"

# Stop WebSocket service 
echo "🛑 Stopping WebSocket service..."
pkill -9 -f "start_websocket_service.py" 2>/dev/null && echo "   ✓ WebSocket service stopped" || echo "   ℹ️  WebSocket service was not running"

# Note: Discord bot was already killed with the aggressive method above
echo "   ✅ Discord bot and proxy already terminated by aggressive kill"

# Wait a moment for processes to fully terminate
sleep 2

# Final verification
echo ""
echo "📊 Final verification..."
PYTHON_COUNT=$(tasklist.exe //FI "IMAGENAME eq python.exe" 2>/dev/null | wc -l)
if [ "$PYTHON_COUNT" -le 1 ]; then
    echo "   ✅ No Python processes detected"
else
    echo "   ⚠️  Still found Python processes:"
    tasklist.exe //FI "IMAGENAME eq python.exe" 2>/dev/null
fi

# Check WSL services
BACKEND_REMAINING=$(ps aux | grep "python main.py" | grep -v grep)
WEBSOCKET_REMAINING=$(ps aux | grep "start_websocket_service.py" | grep -v grep) 
DASHBOARD_REMAINING=$(ps aux | grep -E "(npm run dev|vite)" | grep -v grep)

if [ -z "$BACKEND_REMAINING" ] && [ -z "$WEBSOCKET_REMAINING" ] && [ -z "$DASHBOARD_REMAINING" ]; then
    echo "   ✅ All WSL services stopped successfully"
else
    echo "   ⚠️  Some WSL processes may still be running:"
    [ ! -z "$BACKEND_REMAINING" ] && echo "      Backend processes found"
    [ ! -z "$WEBSOCKET_REMAINING" ] && echo "      WebSocket service found"
    [ ! -z "$DASHBOARD_REMAINING" ] && echo "      Dashboard processes found"
fi

echo ""
echo "💡 If Discord bot still appears online:"
echo "   1. It may take 1-2 minutes for Discord to update status"
echo "   2. Check Discord server - bot should show as offline"
echo "   3. Bot will auto-disconnect from voice channels when process dies"
echo ""
echo "✅ Aggressive shutdown complete"