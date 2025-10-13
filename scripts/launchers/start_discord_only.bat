@echo off
echo 🤖 Starting Discord Bot Only

REM Kill any existing Discord bot
powershell.exe -ExecutionPolicy Bypass -File kill_discord_bots.ps1 2>nul

REM Wait a moment
timeout /t 3 /nobreak >nul

REM Change to Discord bot directory
cd /d "C:\Users\dfoss\Desktop\LocalAIModels\Assistant\WindowsDiscordBot"

REM Start Discord bot
echo ✅ Starting Discord bot...
bot_venv_windows\Scripts\python.exe direct_audio_bot_working.py

echo ❌ Discord bot stopped