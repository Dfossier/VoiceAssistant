#!/bin/bash

echo "⏹️  Stopping Local AI Assistant System"
echo "====================================="

# Stop backend
echo "🛑 Stopping backend..."
pkill -f "python main.py" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ Backend stopped"
else
    echo "   ℹ️  Backend was not running"
fi

# Stop dashboard
echo "🛑 Stopping dashboard..."
pkill -f "npm run dev" 2>/dev/null
pkill -f "vite" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ Dashboard stopped"
else
    echo "   ℹ️  Dashboard was not running"
fi

# Check for any remaining processes
echo ""
echo "📊 Checking for remaining processes..."
REMAINING=$(ps aux | grep -E "(python main.py|npm run dev|vite)" | grep -v grep)
if [ -z "$REMAINING" ]; then
    echo "   ✅ All services stopped successfully"
else
    echo "   ⚠️  Some processes may still be running:"
    echo "$REMAINING"
fi

echo ""
echo "✅ System shutdown complete"