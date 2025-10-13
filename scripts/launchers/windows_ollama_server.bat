@echo off
REM Windows Ollama Quick Setup for Local AI Models

echo ===================================
echo Ollama AI Model Server Setup
echo ===================================
echo.

REM Check if Ollama is installed
where ollama >nul 2>&1
if errorlevel 1 (
    echo Ollama not found!
    echo.
    echo Please download and install from:
    echo https://ollama.com/download/windows
    echo.
    pause
    exit /b 1
)

echo Ollama is installed!
echo.

REM Pull the model if not already available
echo Checking for deepseek-coder model...
ollama list | findstr "deepseek-coder" >nul
if errorlevel 1 (
    echo Downloading deepseek-coder model...
    ollama pull deepseek-coder:1.3b
)

echo.
echo ===================================
echo Ollama server is running!
echo ===================================
echo.
echo API available at: http://localhost:11434
echo.
echo To test in browser:
echo http://localhost:11434/api/tags
echo.
echo Your Discord bot will now use this AI model!
echo.
echo Keep this window open while using the bot.
echo Press Ctrl+C to stop.
echo.

REM Keep window open
pause >nul