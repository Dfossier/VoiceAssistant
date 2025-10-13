#!/bin/bash

echo "🔥 NUCLEAR OPTION: Force kill all Discord bot processes"
echo "====================================================="

# Kill ALL Python processes on Windows (nuclear option)
echo "🔥 Killing ALL Python processes on Windows..."
powershell.exe -Command "Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null && echo "   ✓ Killed all Windows Python" || echo "   ℹ️  No Windows Python found"

# Kill all cmd.exe processes that might be running bots
echo "🔥 Killing suspicious cmd.exe processes..."
taskkill.exe //F //IM cmd.exe //FI "COMMANDLINE eq *python*" 2>/dev/null && echo "   ✓ Killed Python-related cmd.exe" || echo "   ℹ️  No Python cmd.exe found"

# Kill WSL wrapper processes
echo "🔥 Killing WSL wrapper processes..."
pkill -9 -f "/init" 2>/dev/null && echo "   ✓ Killed WSL init processes" || echo "   ℹ️  No WSL init found"
pkill -9 -f "cmd.exe" 2>/dev/null && echo "   ✓ Killed WSL cmd processes" || echo "   ℹ️  No WSL cmd found"

# Kill any discord related processes
echo "🔥 Killing Discord-related processes..."
pkill -9 -f "discord" 2>/dev/null && echo "   ✓ Killed Discord processes" || echo "   ℹ️  No Discord processes found"
pkill -9 -f "bot" 2>/dev/null && echo "   ✓ Killed bot processes" || echo "   ℹ️  No bot processes found"

# Final verification
echo ""
echo "📊 Final verification..."
PYTHON_COUNT=$(tasklist.exe //FI "IMAGENAME eq python.exe" 2>/dev/null | wc -l)
if [ "$PYTHON_COUNT" -le 1 ]; then
    echo "   ✅ No Python processes detected"
else
    echo "   ⚠️  Still found Python processes:"
    tasklist.exe //FI "IMAGENAME eq python.exe" 2>/dev/null
fi

echo ""
echo "💡 If Discord bot still appears online:"
echo "   1. It may take 1-2 minutes for Discord to update status"
echo "   2. Check Discord server - bot should show as offline"
echo "   3. Bot will auto-disconnect from voice channels when process dies"
echo ""
echo "✅ Nuclear cleanup complete"