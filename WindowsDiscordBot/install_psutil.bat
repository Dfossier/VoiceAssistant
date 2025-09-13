@echo off
echo Installing psutil for bot management...
echo.

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing psutil...
pip install psutil

echo.
echo ✅ psutil installed successfully!
echo.
echo You can now use: manage_bot.bat start
pause