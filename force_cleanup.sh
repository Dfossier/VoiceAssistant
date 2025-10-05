#!/bin/bash

echo "🧹 FORCE CLEANUP - Killing ALL services"
echo "======================================"

# Kill all Python main.py processes
echo "Killing all backend processes..."
pkill -9 -f "python main.py"
pkill -9 -f "pt_main_thread"

# Kill all npm/node/vite processes
echo "Killing all dashboard processes..."
pkill -9 -f "npm"
pkill -9 -f "vite"
pkill -9 -f "node"
pkill -9 -f "esbuild"

# Kill anything on our ports
echo "Killing processes on ports..."
for port in 8000 8002 3000 3001 5173; do
    lsof -ti:$port | xargs -r kill -9 2>/dev/null
done

# Kill Discord bot on Windows
echo "Killing Discord bot..."
taskkill.exe //F //IM python.exe 2>/dev/null || true

# Wait a moment
sleep 3

# Clean up zombie processes
echo "Cleaning up zombies..."
ps aux | grep "<defunct>" | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true

# Verify everything is dead
echo ""
echo "Verification:"
echo "============="
echo "Python processes:"
ps aux | grep "python main.py" | grep -v grep || echo "  None found ✓"
echo ""
echo "Dashboard processes:" 
ps aux | grep -E "npm|vite|node" | grep -v grep | wc -l | xargs -I{} echo "  {} processes remaining"
echo ""
echo "Port usage:"
lsof -i:8000,8002,3000,3001,5173 | grep LISTEN || echo "  All ports free ✓"

echo ""
echo "✅ Force cleanup complete"