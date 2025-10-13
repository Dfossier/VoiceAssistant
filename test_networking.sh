#!/bin/bash

echo "🔍 Testing WSL2 Mirrored Networking"
echo "==================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if backend is running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend accessible from WSL${NC}"
else
    echo -e "${YELLOW}⚠️  Backend not running - start with ./start.sh${NC}"
    exit 1
fi

# Test WebSocket connection
echo "Testing WebSocket connection..."
python3 -c "
import asyncio
import websockets
import json

async def test():
    try:
        async with websockets.connect('ws://127.0.0.1:8000/ws') as ws:
            print('✅ WebSocket connection successful!')
            await ws.send(json.dumps({'type': 'start'}))
            response = await ws.recv()
            print('✅ WebSocket response received')
            return True
    except Exception as e:
        print('❌ WebSocket connection failed:', str(e))
        return False

result = asyncio.run(test())
" 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Mirrored networking is working!${NC}"
    echo -e "${GREEN}✅ Discord bot should now connect successfully${NC}"
else
    echo -e "${RED}❌ Mirrored networking test failed${NC}"
    echo -e "${YELLOW}ℹ️  Run enable_mirrored_networking.ps1 as Administrator${NC}"
fi
