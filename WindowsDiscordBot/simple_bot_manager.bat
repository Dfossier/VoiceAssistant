@echo off
title Discord Bot Manager
cd /d "%~dp0"

:menu
cls
echo ========================================
echo         DISCORD BOT MANAGER
echo ========================================
echo.
echo Current Status:
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "bot.py" >NUL
if %ERRORLEVEL% EQU 0 (
    echo [✓] Bot is RUNNING
) else (
    echo [X] Bot is STOPPED
)
echo.
echo ========================================
echo 1. START Bot
echo 2. STOP Bot (Clean shutdown)
echo 3. RESTART Bot
echo 4. VIEW Logs
echo 5. KILL All Python processes
echo 6. EXIT
echo ========================================
echo.
set /p choice="Select option (1-6): "

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto restart
if "%choice%"=="4" goto logs
if "%choice%"=="5" goto killall
if "%choice%"=="6" exit
goto menu

:start
echo.
echo Starting Discord Bot...
call venv\Scripts\activate.bat
start /B python bot.py > bot_output.log 2>&1
timeout /t 3 >NUL
echo Bot started!
pause
goto menu

:stop
echo.
echo Stopping Discord Bot gracefully...

REM First try graceful shutdown
taskkill /IM python.exe /FI "MEMUSAGE gt 30000" >NUL 2>&1
timeout /t 3 >NUL

REM Check if still running
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "python.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    echo Bot didn't stop gracefully, force killing...
    taskkill /F /IM python.exe /FI "MEMUSAGE gt 30000" >NUL 2>&1
)

REM Kill any remaining Discord bot processes
wmic process where "name='python.exe' and commandline like '%%bot.py%%'" delete >NUL 2>&1

timeout /t 2 >NUL
echo Bot stopped!
echo NOTE: Bot may still appear online in Discord for up to 30 seconds
pause
goto menu

:restart
call :stop
timeout /t 2 >NUL
call :start
goto menu

:logs
echo.
echo === LAST 50 LINES OF LOG ===
echo.
powershell -command "Get-Content logs\discord_bot.log -Tail 50"
echo.
pause
goto menu

:killall
echo.
echo WARNING: This will kill ALL Python processes!
set /p confirm="Are you sure? (Y/N): "
if /i "%confirm%"=="Y" (
    taskkill /F /IM python.exe /T >NUL 2>&1
    echo All Python processes killed!
) else (
    echo Cancelled.
)
pause
goto menu