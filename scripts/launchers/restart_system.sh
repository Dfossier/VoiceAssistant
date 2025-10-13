#!/bin/bash
# Restart system with clean state

echo "🔄 Restarting Local AI Assistant System"
echo "======================================"

# First shutdown everything
echo "1️⃣ Shutting down existing services..."
./shutdown_all.sh

# Wait a moment
echo ""
echo "⏳ Waiting for clean state..."
sleep 3

# Start backend API
echo ""
echo "2️⃣ Starting Backend API..."
cd /mnt/c/users/dfoss/desktop/localaimodels/assistant
source venv/bin/activate

# Use the test API for now (simpler, doesn't block)
echo "   Starting simplified API server..."
python test_api.py > backend_api.log 2>&1 &
BACKEND_PID=$!
echo "   ✅ API started (PID: $BACKEND_PID)"

# Wait for API to be ready
echo "   ⏳ Waiting for API to initialize..."
for i in {1..10}; do
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo "   ✅ API is ready!"
        break
    fi
    sleep 1
done

# Start dashboard
echo ""
echo "3️⃣ Starting Web Dashboard..."
cd web-dashboard
npm run dev > ../dashboard.log 2>&1 &
DASHBOARD_PID=$!
cd ..
echo "   ✅ Dashboard started (PID: $DASHBOARD_PID)"

# Display status
echo ""
echo "✅ System Restarted Successfully!"
echo "=================================="
echo ""
echo "📊 Service Status:"
echo "   • API Server:  Running on http://localhost:8000 (PID: $BACKEND_PID)"
echo "   • Dashboard:   Running on http://localhost:3001 (PID: $DASHBOARD_PID)"
echo ""
echo "🌐 Access Points:"
echo "   • Dashboard:   http://localhost:3001"
echo "   • API Docs:    http://localhost:8000/docs"
echo "   • Health:      http://localhost:8000/health"
echo ""
echo "📝 Logs:"
echo "   • Backend:     tail -f backend_api.log"
echo "   • Dashboard:   tail -f dashboard.log"
echo ""
echo "🛑 To stop:       ./shutdown_all.sh"
echo "🔄 To restart:    ./restart_system.sh"
echo ""
echo "Dashboard should open automatically in your browser..."

# Optional: Try to open browser (works on some systems)
if command -v xdg-open >/dev/null 2>&1; then
    sleep 3
    xdg-open http://localhost:3001 2>/dev/null &
fi