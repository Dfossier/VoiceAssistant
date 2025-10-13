# Justfile for Local AI Assistant Project
# Run commands with: just <command>

# Start Discord bot in background on Windows
discord-start-bg:
    echo "🚀 Starting Discord bot in background..."
    cd /mnt/c/Users/dfoss/Desktop/LocalAIModels/Assistant/WindowsDiscordBot && cmd.exe /c "start /B bot_venv_windows\\Scripts\\python direct_audio_bot.py" 2>/dev/null || true
    echo "✅ Discord bot started in background"
    echo "💡 Use 'just discord-stop-bg' to stop it"

# Stop Discord bot background process
discord-stop-bg:
    echo "🛑 Stopping Discord bot background processes..."
    taskkill.exe //F //IM python.exe //FI "COMMANDLINE eq *direct_audio_bot.py*" 2>/dev/null || true
    pkill -f "direct_audio_bot.py" 2>/dev/null || true
    echo "✅ Discord bot processes stopped"

# Start backend server in background
backend-start:
    echo "🚀 Starting backend server..."
    bash -c "source venv/bin/activate && python main.py > backend.log 2>&1 &"
    echo "✅ Backend started in background"
    echo "📋 Check logs: tail -f backend.log"

# Stop backend server
backend-stop:
    echo "🛑 Stopping backend server..."
    pkill -f "python main.py" || true
    echo "✅ Backend stopped"

# Show backend logs
backend-logs:
    tail -f backend.log

# Full system start (backend + discord bot)
start-all: backend-start discord-start-bg
    echo "🚀 All services started!"
    echo "📋 Backend logs: just backend-logs"
    echo "🎤 Join Discord voice channel and use: !direct"

# Full system stop
stop-all: discord-stop-bg backend-stop
    echo "🛑 All services stopped"

# Check system status
status:
    echo "📊 System Status:"
    echo "Backend (Python):"
    ps aux | grep "python main.py" | grep -v grep || echo "  ❌ Not running"
    echo "Discord Bot:"
    tasklist.exe //FI "IMAGENAME eq python.exe" 2>/dev/null | grep -i python || echo "  ❌ Not running"

# Clean up log files
clean-logs:
    rm -f backend.log backend_*.log *.log 2>/dev/null || true
    echo "✅ Log files cleaned"