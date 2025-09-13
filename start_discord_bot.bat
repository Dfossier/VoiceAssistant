@echo off
echo Starting Discord Bot on Native Windows...
echo.

cd WindowsDiscordBot

echo Checking for virtual environment...
if not exist venv (
    echo Virtual environment not found. Running setup...
    call setup_windows.bat
)

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Starting Discord bot...
python bot.py

pause