@echo off
title AI Assistant Services
color 0A
echo.
echo ========================================
echo   AI Assistant - Service Launcher
echo ========================================
echo.

echo Checking current status...

REM Check if backend is running
curl -s http://127.0.0.1:8000/health > nul 2>&1
if %ERRORLEVEL% == 0 (
    echo [✓] Backend API: Running at http://127.0.0.1:8000
    set BACKEND_RUNNING=1
) else (
    echo [✗] Backend API: Stopped
    set BACKEND_RUNNING=0
)

REM Check if Discord bot virtual environment exists
if exist "WindowsDiscordBot\venv\Scripts\python.exe" (
    echo [✓] Discord Bot: Virtual environment ready
    set BOT_READY=1
) else (
    echo [✗] Discord Bot: Virtual environment missing
    set BOT_READY=0
)

echo.

if %BACKEND_RUNNING%==0 (
    echo Starting WSL Backend API...
    echo.
    start "Backend API" wsl -d Ubuntu bash -c "cd /mnt/c/users/dfoss/desktop/localaimodels/assistant && python3 main.py"
    
    echo Waiting for backend to start...
    :wait_backend
    timeout /t 2 > nul
    curl -s http://127.0.0.1:8000/health > nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo Still waiting...
        goto wait_backend
    )
    echo [✓] Backend started successfully!
    echo.
)

if %BOT_READY%==0 (
    echo [!] Setting up Discord Bot environment...
    cd WindowsDiscordBot
    call setup_windows.bat
    cd ..
    echo.
)

echo Starting Discord Bot...
cd WindowsDiscordBot
start "Discord Bot" cmd /k "venv\Scripts\activate && python bot.py"
cd ..

echo.
echo ========================================
echo   Services Started!
echo ========================================
echo.
echo Backend API:  http://127.0.0.1:8000
echo Discord Bot:  Check new window
echo.
echo To use the simple CLI manager:
echo   python simple_service_manager.py
echo.
echo Press any key to exit this launcher...
pause > nul