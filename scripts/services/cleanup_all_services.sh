#!/bin/bash
echo "🧹 Comprehensive Service Cleanup"

# Kill all Python AI assistant processes
echo "Stopping Python processes..."
pkill -f "run_api" 2>/dev/null || true
pkill -f "run_voice" 2>/dev/null || true  
pkill -f "python main.py" 2>/dev/null || true
pkill -f "direct_audio_bot" 2>/dev/null || true

# Kill all Node/Vite processes in the project
echo "Stopping Node/Vite processes..."
pkill -f "web-dashboard.*vite" 2>/dev/null || true
pkill -f "web-dashboard.*node" 2>/dev/null || true
pkill -f "web-dashboard.*esbuild" 2>/dev/null || true

# Kill Discord bot processes on Windows
echo "Stopping Discord bot processes..."
powershell.exe -ExecutionPolicy Bypass -File kill_discord_bots.ps1 2>/dev/null || true

# Check for any processes still using our ports
echo "Checking port usage..."
for port in 8000 8001 8002 3000 3001; do
    pid=$(lsof -ti:$port 2>/dev/null || true)
    if [ ! -z "$pid" ]; then
        echo "Killing process on port $port (PID: $pid)"
        kill -9 $pid 2>/dev/null || true
    fi
done

# Wait for processes to fully terminate
sleep 3

echo "✅ Cleanup complete"
echo "Checking remaining processes..."
ps aux | grep -E "(python.*run_|python.*main\.py|node.*vite|direct_audio)" | grep -v grep || echo "No related processes found"