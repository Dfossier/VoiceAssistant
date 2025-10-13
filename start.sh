#!/bin/bash

echo "🚀 Starting Local AI Assistant"
echo "=============================="
echo ""

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print status messages
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "minimal_main.py" ]; then
    print_error "Please run this script from the Local AI Assistant directory"
    exit 1
fi

# Kill any existing processes
print_status "Cleaning up existing processes..."
pkill -f "python3 minimal_main.py" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 2

# Activate virtual environment for CUDA support
if [ -d "venv" ]; then
    print_status "Activating virtual environment for CUDA acceleration..."
    source venv/bin/activate
    print_success "Virtual environment activated with CUDA support"
else
    print_warning "No virtual environment found - using system Python"
fi

# Check Python availability
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed or not in PATH"
    exit 1
fi

# Check for CUDA availability
python3 -c "import torch; print(f'🔥 CUDA Available: {torch.cuda.is_available()}'); print(f'🚀 GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU Only\"}')" 2>/dev/null || print_warning "PyTorch not available for CUDA check"

print_status "Starting backend server..."
python3 minimal_main.py > backend.log 2>&1 &
BACKEND_PID=$!

# Wait for server to start
print_status "Waiting for server to initialize..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:8888/health > /dev/null 2>&1; then
        print_success "Backend server is running on http://127.0.0.1:8888"
        break
    fi
    
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        print_error "Backend server failed to start. Check backend.log"
        cat backend.log
        exit 1
    fi
    
    echo -n "."
    sleep 1
done

if ! curl -s http://127.0.0.1:8888/health > /dev/null 2>&1; then
    print_warning "Backend server started but health check failed"
    print_warning "Server may still be initializing..."
fi

# Start web dashboard (optional)
if [ -d "web-dashboard" ] && [ -f "web-dashboard/package.json" ]; then
    print_status "Starting web dashboard..."
    cd web-dashboard
    if command -v npm &> /dev/null; then
        npm run dev > ../dashboard.log 2>&1 &
        DASHBOARD_PID=$!
        cd ..
        print_success "Web dashboard started (may take a moment to compile)"
    else
        print_warning "npm not found - web dashboard not started"
        cd ..
    fi
fi

echo ""
print_success "Local AI Assistant Started Successfully!"
echo ""
echo "🌐 Backend API:    http://127.0.0.1:8888"
echo "🔧 Health Check:   http://127.0.0.1:8888/health"
echo "📊 Logs:           tail -f backend.log"
if [ ! -z "$DASHBOARD_PID" ]; then
    echo "🖥️  Web Dashboard: http://localhost:3000"
    echo "📊 Dashboard Logs: tail -f dashboard.log"
fi
echo ""
echo "🎤 Discord Bot: Run from Windows:"
echo "   ℹ️  Uses mirrored networking: ws://127.0.0.1:8888"
echo "   cd WindowsDiscordBot"
echo "   bot_venv_windows\\Scripts\\python direct_audio_bot_working.py"
echo ""
echo "🛑 To stop: ./stop.sh"
echo ""
print_status "Press Ctrl+C to stop all services"

# Wait for user interrupt
trap "echo ''; print_status 'Shutting down...'; ./stop.sh 2>/dev/null; exit 0" INT
wait
