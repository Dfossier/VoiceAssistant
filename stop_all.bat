@echo off
echo Stopping AI Assistant Services...
echo.

echo [1/2] Stopping Discord Bot processes...
taskkill /f /im python.exe 2>nul
taskkill /f /im pythonw.exe 2>nul

echo [2/2] Stopping WSL Backend API...
wsl -d Ubuntu bash -c "pkill -f 'python3.*main.py' || true"

echo.
echo All services stopped!
pause