@echo off
echo Downloading Opus library for Discord voice...

REM Download opus.dll from Discord's CDN
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://cdn.discordapp.com/attachments/958352130717913098/958352194278449162/libopus-0.x64.dll' -OutFile 'opus.dll'}"

if exist opus.dll (
    echo.
    echo Successfully downloaded opus.dll
    echo.
    echo Now placing it in the bot directory...
    copy opus.dll venv\Scripts\opus.dll
    
    echo.
    echo Opus library installed!
    echo Restart the bot and voice should work.
) else (
    echo.
    echo Failed to download opus.dll
    echo.
    echo Alternative: Download manually from:
    echo https://opus-codec.org/downloads/
)

pause