#!/bin/bash
# Clean shutdown script for all services

echo "🛑 Shutting down all services..."
echo "================================"

# Kill Python processes (backend, API servers)
echo "📍 Stopping Python processes..."
pkill -f "python.*test_api.py" 2>/dev/null && echo "   ✅ Test API stopped"
pkill -f "uvicorn.*server" 2>/dev/null && echo "   ✅ Uvicorn servers stopped"
pkill -f "python.*main.py" 2>/dev/null && echo "   ✅ Main backend stopped"
pkill -f "python.*main_coordinated.py" 2>/dev/null && echo "   ✅ Coordinated backend stopped"

# Kill Node/NPM processes (dashboard)
echo ""
echo "📍 Stopping Node processes..."
pkill -f "npm run dev" 2>/dev/null && echo "   ✅ NPM dev stopped"
pkill -f "node.*vite" 2>/dev/null && echo "   ✅ Vite stopped"
pkill -f "esbuild" 2>/dev/null && echo "   ✅ ESBuild stopped"

# Wait for processes to exit
echo ""
echo "⏳ Waiting for processes to terminate..."
sleep 2

# Check for lingering processes on ports
echo ""
echo "📍 Checking ports..."
for port in 8000 8002 3000 3001; do
    if lsof -i :$port >/dev/null 2>&1; then
        echo "   ⚠️  Port $port still in use, force closing..."
        fuser -k $port/tcp 2>/dev/null
    else
        echo "   ✅ Port $port is free"
    fi
done

# Final check
echo ""
echo "📊 Final Status Check:"
echo "====================="

# Check if any processes are still running
REMAINING_PYTHON=$(pgrep -f "python.*(main|test_api|uvicorn)" 2>/dev/null)
REMAINING_NODE=$(pgrep -f "(npm|node|vite)" 2>/dev/null)

if [ -z "$REMAINING_PYTHON" ] && [ -z "$REMAINING_NODE" ]; then
    echo "✅ All services successfully stopped!"
else
    echo "⚠️  Some processes may still be running:"
    [ ! -z "$REMAINING_PYTHON" ] && echo "   Python PIDs: $REMAINING_PYTHON"
    [ ! -z "$REMAINING_NODE" ] && echo "   Node PIDs: $REMAINING_NODE"
    echo ""
    echo "Run 'ps aux | grep -E \"python|node\"' to check"
fi

echo ""
echo "🧹 Cleanup complete! You can now restart services."