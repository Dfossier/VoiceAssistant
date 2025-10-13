#!/bin/bash
set -e

echo "🚀 Starting Production AI Assistant System"
echo "=========================================="

# Function to check if port is available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "❌ Port $port is in use"
        return 1
    else
        echo "✅ Port $port is available"
        return 0
    fi
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local timeout=${2:-30}
    local count=0
    
    echo "⏳ Waiting for $url to be ready..."
    while [ $count -lt $timeout ]; do
        if curl -s -f "$url" >/dev/null 2>&1; then
            echo "✅ Service at $url is ready"
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done
    echo "❌ Service at $url failed to start within ${timeout}s"
    return 1
}

# Function to wait for backend with model loading
wait_for_backend_ready() {
    local timeout=${1:-180}
    local count=0
    
    echo "⏳ Waiting for backend to load all models (this may take 2-3 minutes)..."
    while [ $count -lt $timeout ]; do
        response=$(curl -s http://localhost:8000/health 2>/dev/null || echo '{"status":"error"}')
        status=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 2>/dev/null || echo "error")
        
        if [ "$status" = "healthy" ]; then
            echo "✅ Backend is ready with all models loaded"
            return 0
        elif [ "$status" = "loading" ]; then
            echo "⏳ Models still loading... ($count/${timeout}s)"
        elif [ "$status" = "initializing" ]; then
            echo "⏳ Backend initializing... ($count/${timeout}s)"
        fi
        
        sleep 1
        count=$((count + 1))
    done
    echo "❌ Backend failed to load models within ${timeout}s"
    return 1
}

# Step 1: Complete cleanup
echo -e "\n🧹 Step 1: Complete System Cleanup"
./cleanup_all_services.sh

# Step 2: Verify all ports are available
echo -e "\n🔍 Step 2: Port Availability Check"
REQUIRED_PORTS=(8000 3000)
for port in "${REQUIRED_PORTS[@]}"; do
    if ! check_port $port; then
        echo "❌ Port conflict detected. Attempting to free port $port..."
        pid=$(lsof -ti:$port 2>/dev/null || true)
        if [ ! -z "$pid" ]; then
            kill -9 $pid 2>/dev/null || true
            sleep 2
        fi
        if ! check_port $port; then
            echo "❌ Failed to free port $port. Exiting."
            exit 1
        fi
    fi
done

# Step 3: Start backend with fixed Kokoro
echo -e "\n🚀 Step 3: Starting Production Backend"
cd /mnt/c/users/dfoss/desktop/localaimodels/assistant
source venv/bin/activate

# Remove any existing backend logs
rm -f backend_production.log

# Start backend in background
nohup python main.py > backend_production.log 2>&1 &
BACKEND_PID=$!
echo "Backend started with PID: $BACKEND_PID"

# Wait for backend to be ready (it takes time to load models)
if wait_for_backend_ready 180; then
    echo "✅ All models loaded successfully"
else
    echo "⚠️  Backend is taking longer than expected to load models"
    echo "Last 20 lines of backend log:"
    tail -20 backend_production.log
    
    # Check if backend process is still running
    if kill -0 $BACKEND_PID 2>/dev/null; then
        echo "⚠️  Backend is still running (PID: $BACKEND_PID) - continuing with other services"
        echo "⚠️  You may need to wait a bit longer for models to fully load"
    else
        echo "❌ Backend process has died - exiting"
        exit 1
    fi
fi

# Step 4: Start web dashboard
echo -e "\n🖥️  Step 4: Starting Web Dashboard"
cd web-dashboard

# Kill any existing vite processes
pkill -f "web-dashboard.*vite" 2>/dev/null || true
sleep 2

# Start web dashboard
nohup npm run dev > ../web_dashboard.log 2>&1 &
WEB_PID=$!
echo "Web dashboard started with PID: $WEB_PID"

# Wait for web dashboard
if wait_for_service "http://localhost:3000" 30; then
    echo "✅ Web dashboard is ready"
else
    echo "⚠️  Web dashboard may not be ready yet (check manually)"
fi

cd ..

# Step 5: Start Discord bot
echo -e "\n🤖 Step 5: Starting Discord Bot"
just discord-start-bg

sleep 5

# Step 6: Final system check
echo -e "\n📊 Step 6: Final System Status"
echo "=========================================="

# Check backend
if curl -s -f "http://localhost:8000/health" >/dev/null 2>&1; then
    echo "✅ Backend API (port 8000): Running"
else
    echo "❌ Backend API (port 8000): Not responding"
fi

# Check voice pipeline
if timeout 5 bash -c "</dev/tcp/172.20.104.13/8002" 2>/dev/null; then
    echo "✅ Voice Pipeline (port 8002): Running"
else
    echo "❌ Voice Pipeline (port 8002): Not responding"
fi

# Check web dashboard
if curl -s -f "http://localhost:3000" >/dev/null 2>&1; then
    echo "✅ Web Dashboard (port 3000): Running"
else
    echo "❌ Web Dashboard (port 3000): Not responding"
fi

# Check Discord bot
DISCORD_COUNT=$(wmic.exe process where "name='python.exe' and CommandLine like '%direct_audio_bot%'" get ProcessId /value 2>/dev/null | grep -c "ProcessId=" || echo "0")
if [ "$DISCORD_COUNT" -gt 0 ]; then
    echo "✅ Discord Bot: Running ($DISCORD_COUNT instance(s))"
else
    echo "❌ Discord Bot: Not running"
fi

echo -e "\n🎉 Production System Startup Complete!"
echo "=========================================="
echo "🌐 Web Interface: http://localhost:3000"
echo "🔌 API Endpoint: http://localhost:8000"
echo "🎤 Voice Pipeline: ws://172.20.104.13:8002"
echo "📋 Backend Logs: tail -f backend_production.log"
echo "📋 Web Logs: tail -f web_dashboard.log"
echo -e "\n💡 Use 'just status' to check system status anytime"