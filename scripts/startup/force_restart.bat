@echo off
title Force Restart AI Assistant Services
color 0C
echo.
echo ==========================================
echo   FORCE RESTART - AI Assistant Services
echo ==========================================
echo.
echo WARNING: This will forcefully kill all processes
echo and restart with fresh connections.
echo.
pause

echo Killing all Discord bot processes...
taskkill /f /im python.exe >nul 2>&1
echo Done.

echo Killing WSL backend processes...
wsl pkill -f "python3.*main.py" >nul 2>&1
echo Done.

echo Waiting 3 seconds for cleanup...
timeout /t 3 >nul

echo.
echo Starting fresh services...
echo.

REM Start WSL backend
echo Starting WSL Backend...
start "Backend API" wsl -d Ubuntu bash -c "cd /mnt/c/users/dfoss/desktop/localaimodels/assistant && python3 main.py"

echo Waiting for backend to initialize...
timeout /t 5 >nul

REM Check if backend started
curl -s http://127.0.0.1:8000/health > nul 2>&1
if %ERRORLEVEL% == 0 (
    echo [✓] Backend started successfully
) else (
    echo [✗] Backend failed to start
    echo Please check logs manually
    pause
    exit /b 1
)

echo.
echo Starting Discord Bot...
cd WindowsDiscordBot
start "Discord Bot" cmd /k "venv\Scripts\activate && python bot.py"
cd ..

echo.
echo ==========================================
echo   Services Restarted!
echo ==========================================
echo.
echo Backend API: http://127.0.0.1:8000
echo Discord Bot: Check new window
echo.
echo Try these commands in Discord:
echo   !help
echo   !status  
echo   !force_disconnect (if bot stuck in voice)
echo.
pause