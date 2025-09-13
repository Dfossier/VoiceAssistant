@echo off
setlocal

if "%1"=="" (
    echo Discord Bot Manager
    echo.
    echo Usage: manage_bot.bat [start^|stop^|restart^|monitor]
    echo.
    echo   start   - Start the Discord bot
    echo   stop    - Stop the Discord bot
    echo   restart - Restart the Discord bot
    echo   monitor - Start bot with auto-restart on crash
    echo.
    pause
    exit /b 1
)

cd /d "%~dp0"

echo Activating virtual environment...
call venv\Scripts\activate.bat

if "%1"=="start" (
    echo Starting Discord Bot...
    python bot_manager.py start
) else if "%1"=="stop" (
    echo Stopping Discord Bot...
    python bot_manager.py stop
) else if "%1"=="restart" (
    echo Restarting Discord Bot...
    python bot_manager.py restart
) else if "%1"=="monitor" (
    echo Starting Bot Monitor...
    python bot_manager.py monitor
) else (
    echo Invalid action: %1
    echo Use: start, stop, restart, or monitor
    pause
    exit /b 1
)

if "%1"=="start" (
    echo.
    echo Bot is running. To view logs:
    echo   type logs\discord_bot.log
    echo.
    echo To stop the bot:
    echo   manage_bot.bat stop
)

pause