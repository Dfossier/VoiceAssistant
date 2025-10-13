#!/bin/bash

echo "🛑 Stopping Local AI Assistant"
echo "=============================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Kill backend server
print_status "Stopping backend server..."
pkill -f "python3 minimal_main.py" 2>/dev/null && print_success "Backend stopped" || print_status "Backend not running"

# Kill web dashboard
print_status "Stopping web dashboard..."
pkill -f "vite" 2>/dev/null && print_success "Dashboard stopped" || print_status "Dashboard not running"
pkill -f "node.*vite" 2>/dev/null || true

# Kill any remaining Python processes
print_status "Cleaning up remaining processes..."
pkill -f "python3.*main.py" 2>/dev/null || true

print_success "All services stopped"
