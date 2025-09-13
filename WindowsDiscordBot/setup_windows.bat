@echo off
echo Setting up Windows Discord Bot Environment...
echo.

echo [1/4] Checking Python installation...
python --version
if errorlevel 1 (
    echo ERROR: Python not found! Please install Python 3.11+ from python.org
    pause
    exit /b 1
)

echo.
echo [2/4] Creating virtual environment...
if exist venv (
    echo Virtual environment already exists, skipping...
) else (
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment!
        pause
        exit /b 1
    )
)

echo.
echo [3/4] Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies!
    pause
    exit /b 1
)

echo.
echo [4/4] Creating logs directory...
mkdir logs 2>nul

echo.
echo ✅ Windows Discord Bot setup complete!
echo.
echo Next steps:
echo 1. Ensure your .env file in the parent directory contains:
echo    - DISCORD_BOT_TOKEN=your_bot_token
echo    - API_KEY=your_backend_api_key
echo 2. Run: python bot.py
echo.
pause