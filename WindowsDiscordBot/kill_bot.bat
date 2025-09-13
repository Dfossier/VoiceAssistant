@echo off
echo Killing Discord bot processes...

taskkill /F /IM python.exe /T >NUL 2>&1
taskkill /F /IM pythonw.exe /T >NUL 2>&1
taskkill /F /IM py.exe /T >NUL 2>&1

echo Checking for remaining processes...
wmic process where "name like '%%python%%'" get processid,name,commandline 2>NUL | find "bot.py" && (
    echo WARNING: Bot processes still running!
    echo Kill them manually with: taskkill /F /PID [process_id]
) || (
    echo All bot processes terminated.
)

echo.
echo Starting new bot in 3 seconds...
timeout /t 3 >NUL

venv\Scripts\python fix_opus.py