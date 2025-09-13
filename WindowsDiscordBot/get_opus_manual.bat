@echo off
echo.
echo Manual Opus Download Instructions:
echo ==================================
echo.
echo Since automatic download failed, please:
echo.
echo 1. Go to: https://github.com/ImageMagick/libopus/releases
echo    OR
echo    https://archive.mozilla.org/pub/opus/win32/opus-1.1.3-win32.zip
echo.
echo 2. Download the Windows 64-bit version
echo.
echo 3. Extract and find "opus.dll" (might be named libopus.dll)
echo.
echo 4. Copy it to:
echo    - This folder: %CD%
echo    - AND to: %CD%\venv\Scripts\
echo.
echo 5. Rename to "opus.dll" if needed
echo.
echo Alternative - Use Discord's Opus:
echo =================================
echo If you have Discord installed, copy from:
echo %LOCALAPPDATA%\Discord\app-[version]\modules\discord_voice\
echo.
pause