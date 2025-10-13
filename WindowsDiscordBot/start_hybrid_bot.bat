@echo off
echo Starting Hybrid Discord Bot...
echo ===============================
echo.
echo This bot supports both:
echo - Local microphone capture (when you're at your computer)
echo - Remote Discord calling (when you call in from phone)
echo.
echo Auto-detection is enabled by default.
echo.
echo Activating virtual environment...
call bot_venv_windows\Scripts\activate

echo.
echo Starting hybrid bot with auto-mode detection...
echo WebSocket target: ws://127.0.0.1:8002
echo.

python hybrid_discord_bot.py

echo.
echo Bot has stopped. Press any key to exit...
pause