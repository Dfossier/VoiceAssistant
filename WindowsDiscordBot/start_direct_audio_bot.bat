@echo off
echo Starting Discord Direct Audio Bot...
echo ===================================
echo.
echo Activating virtual environment...
call bot_venv_windows\Scripts\activate

echo.
echo Starting bot with direct_audio_bot_working.py...
echo WebSocket target: ws://127.0.0.1:8002
echo.

python direct_audio_bot_working.py

echo.
echo Bot has stopped. Press any key to exit...
pause