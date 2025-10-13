@echo off
echo Killing Discord bot processes...

REM Method 1: Kill by exact command line match
for /f "tokens=2" %%i in ('wmic process where "CommandLine like '%%direct_audio_bot%%'" get ProcessId /value 2^>nul ^| findstr "ProcessId="') do (
    for /f "tokens=2 delims==" %%j in ("%%i") do (
        echo Killing PID %%j
        taskkill /F /PID %%j 2>nul
    )
)

REM Method 2: Kill by WMIC terminate
wmic process where "name='python.exe' and CommandLine like '%%direct_audio%%'" call terminate 2>nul

REM Method 3: Brute force kill by pattern
for /f "tokens=1" %%i in ('tasklist /fi "imagename eq python.exe" /fo table /nh ^| findstr /v "INFO"') do (
    wmic process where "ProcessId=%%i and CommandLine like '%%direct_audio%%'" call terminate 2>nul
)

REM Wait a moment
timeout /t 2 /nobreak >nul

echo Discord bot processes terminated.