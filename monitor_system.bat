@echo off
title System Monitor - AI Assistant
color 0A

:monitor
cls
echo ================================================================================
echo                           AI ASSISTANT SYSTEM MONITOR
echo ================================================================================
echo.

echo [BACKEND API - WSL2]
curl -s http://127.0.0.1:8000/health >NUL 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Status: [✓] RUNNING on port 8000
    curl -s http://127.0.0.1:8000/health
) else (
    echo Status: [X] NOT RUNNING
)
echo.

echo --------------------------------------------------------------------------------
echo.

echo [DISCORD BOT - Windows]
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "bot.py" >NUL
if %ERRORLEVEL% EQU 0 (
    echo Status: [✓] RUNNING
    echo Log file: WindowsDiscordBot\logs\discord_bot.log
) else (
    echo Status: [X] NOT RUNNING
)
echo.

echo --------------------------------------------------------------------------------
echo.

echo [QUICK ACTIONS]
echo 1. Start Backend (WSL2)
echo 2. Start Discord Bot (Windows)  
echo 3. View Backend Logs
echo 4. View Bot Logs
echo 5. Stop Everything
echo 6. Refresh
echo 7. Exit
echo.

set /p action="Select action (1-7): "

if "%action%"=="1" (
    echo Starting backend in WSL2...
    start wsl bash -c "cd /mnt/c/users/dfoss/desktop/localaimodels/assistant && ./start.sh"
    timeout /t 3 >NUL
)
if "%action%"=="2" (
    echo Starting Discord bot...
    cd WindowsDiscordBot
    start cmd /k "venv\Scripts\activate && python bot.py"
    cd ..
    timeout /t 3 >NUL
)
if "%action%"=="3" (
    echo === BACKEND LOGS ===
    type server.log | more
    pause
)
if "%action%"=="4" (
    echo === BOT LOGS ===
    type WindowsDiscordBot\logs\discord_bot.log | more
    pause
)
if "%action%"=="5" (
    echo Stopping all services...
    taskkill /F /IM python.exe /T >NUL 2>&1
    wsl pkill -f "python.*main.py"
    echo All services stopped!
    pause
)
if "%action%"=="6" goto monitor
if "%action%"=="7" exit

goto monitor