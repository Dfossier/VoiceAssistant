@echo off
echo.
echo Official Opus Download Instructions:
echo ====================================
echo.
echo 1. Go to the OFFICIAL Opus site:
echo    https://opus-codec.org/downloads/
echo.
echo 2. Under "Windows Binaries" section, download:
echo    - For 64-bit: opus-1.3.1-win64.zip (or latest version)
echo    - For 32-bit: opus-1.3.1-win32.zip (if needed)
echo.
echo 3. Extract the ZIP file
echo.
echo 4. Look for the DLL file in the extracted folder:
echo    - It might be in a "bin" or "x64" subfolder
echo    - File might be named: opus.dll, libopus.dll, or libopus-0.dll
echo.
echo 5. Copy the DLL file to BOTH locations:
echo    a) %CD% (current bot directory)
echo    b) %CD%\venv\Scripts\
echo.
echo 6. RENAME the file to "opus.dll" if it has a different name
echo.
echo 7. Restart the bot and test with !opustest
echo.
echo Current directory: %CD%
echo.
pause