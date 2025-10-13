@echo off
echo =================================================
echo   AI Assistant - Simple Startup
echo =================================================
echo.

echo [1/2] Starting WSL Backend API (if not already running)...
echo Checking if backend is running...
curl -s http://localhost:8000/health > nul 2>&1
if %ERRORLEVEL% == 0 (
    echo Backend already running at http://localhost:8000
) else (
    echo Starting WSL backend...
    start "WSL Backend" wsl -d Ubuntu bash -c "cd /mnt/c/users/dfoss/desktop/localaimodels/assistant && python3 main.py"
    echo Waiting for backend to start...
    timeout /t 5 > nul
)

echo.
echo [2/2] Starting Windows Discord Bot...
cd /d "%~dp0WindowsDiscordBot"
if not exist venv (
    echo Error: Virtual environment not found!
    echo Please run setup_windows.bat first
    pause
    exit /b 1
)

echo Activating virtual environment and starting bot...
start "Discord Bot" cmd /c "venv\Scripts\activate && python bot.py && pause"

echo.
echo =================================================
echo   Services Started!
echo =================================================
echo.
echo Backend API:     http://localhost:8000
echo Discord Bot:     Check the new window
echo.
echo To stop services:
echo   - Close the Discord Bot window  
echo   - Run: wsl pkill -f "python3.*main.py"
echo.
pause