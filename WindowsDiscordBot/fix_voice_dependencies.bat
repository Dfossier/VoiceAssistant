@echo off
echo Fixing Discord Voice Dependencies...
echo.

echo [1/3] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [2/3] Installing PyNaCl for voice support...
pip install PyNaCl

echo.
echo [3/3] Reinstalling discord.py with voice support...
pip uninstall -y py-cord discord.py
pip install py-cord[voice]

echo.
echo ✅ Voice dependencies fixed!
echo.
echo Now run: python bot.py
pause