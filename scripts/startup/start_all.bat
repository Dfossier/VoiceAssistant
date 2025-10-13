@echo off
echo Starting AI Assistant Services...
echo.

echo [1/2] Starting WSL Backend API...
wsl -d Ubuntu bash -c "cd /mnt/c/users/dfoss/desktop/localaimodels/assistant && nohup python3 main.py > backend.log 2>&1 &"
timeout /t 5 > nul

echo [2/2] Starting Windows Discord Bot...
cd /d "%~dp0WindowsDiscordBot"
start "Discord Bot" python bot.py

echo.
echo Starting Service Manager GUI...
cd /d "%~dp0"
start "Service Manager" python service_manager.py

echo.
echo All services started! Check the Service Manager for status.
pause