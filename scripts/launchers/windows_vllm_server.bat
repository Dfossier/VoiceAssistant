@echo off
REM Windows vLLM Server Launcher for Local AI Models

echo ===================================
echo Starting vLLM Server for Local AI Models
echo ===================================
echo.

cd /d C:\Users\dfoss\Desktop\LocalAIModels

REM Check if vLLM is installed
python -m pip show vllm >nul 2>&1
if errorlevel 1 (
    echo Installing vLLM...
    python -m pip install vllm
)

echo Starting vLLM server with DeepSeek model...
echo Server will run on: http://localhost:8001
echo.

REM Start vLLM with your local model
REM Using the 1.3B model as it's lighter and faster
python -m vllm.entrypoints.openai.api_server ^
    --model ./deepseek-coder-1.3b-instruct-AWQ ^
    --port 8001 ^
    --host 0.0.0.0 ^
    --max-model-len 2048

pause