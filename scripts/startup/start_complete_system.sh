#!/bin/bash
# Complete system startup with proper timing

set -e

echo "🚀 Starting Complete AI Assistant System"
echo "======================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Load configuration
CONFIG_FILE="config/services.json"

# Function to check if process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# 1. Start WebSocket Service (WSL)
echo -e "${YELLOW}Starting WebSocket Service in WSL...${NC}"
if is_running "start_websocket_service"; then
    echo "⚠️  WebSocket service already running"
else
    nohup python3 start_websocket_service.py > websocket_service.log 2>&1 &
    echo "✅ WebSocket service started (PID: $!)"
fi

# 2. Start Backend API (WSL)
echo -e "\n${YELLOW}Starting Backend API in WSL...${NC}"
if is_running "minimal_main.py"; then
    echo "⚠️  Backend API already running"
else
    cd /mnt/c/users/dfoss/desktop/localaimodels/assistant
    nohup python3 minimal_main.py > minimal_server.log 2>&1 &
    echo "✅ Backend API started (PID: $!)"
fi

# 3. Wait for services to be ready
echo -e "\n${YELLOW}Waiting for services to initialize...${NC}"
python3 scripts/startup/wait_for_services.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All WSL services ready!${NC}"
else
    echo -e "${RED}❌ Services failed to start${NC}"
    exit 1
fi

# 4. Start Discord Bot (Windows)
echo -e "\n${YELLOW}Starting Discord Bot on Windows...${NC}"
cd WindowsDiscordBot
cmd.exe /c "start_direct_audio_bot.bat" &

echo -e "\n${GREEN}🎉 Complete system started successfully!${NC}"
echo "===================================="
echo "WebSocket: ws://127.0.0.1:8002"
echo "Backend API: http://127.0.0.1:8000"
echo "Discord Bot: Check Discord for commands (!direct, !stop)"
echo ""
echo "Logs:"
echo "  - WebSocket: websocket_service.log"
echo "  - Backend: minimal_server.log"
echo "  - Discord: WindowsDiscordBot/discord_bot_windows.log"
echo ""
echo "To stop: ./scripts/startup/stop_production_system.sh"