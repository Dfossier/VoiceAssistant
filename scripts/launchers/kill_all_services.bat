@echo off
title Kill All AI Assistant Services
color 0E
echo.
echo ==========================================
echo   KILL ALL SERVICES - Emergency Stop
echo ==========================================
echo.

echo Killing all Python processes...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im pythonw.exe >nul 2>&1

echo Killing WSL processes...  
wsl bash -c "pkill -9 -f 'python3.*main.py'" >nul 2>&1
wsl bash -c "pkill -9 python3" >nul 2>&1

echo Killing any remaining uvicorn processes...
wsl bash -c "pkill -9 -f uvicorn" >nul 2>&1

echo Waiting for cleanup...
timeout /t 5 >nul

echo.
echo ==========================================
echo   ALL SERVICES KILLED
echo ==========================================
echo.
echo All processes stopped. You can now:
echo 1. Use "python simple_service_manager.py" 
echo 2. Or run "start_services.bat"
echo.
pause