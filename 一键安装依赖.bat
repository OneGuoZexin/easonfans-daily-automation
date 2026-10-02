@echo off
setlocal
cd /d "%~dp0"
echo Installing Python dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 goto error
echo Installing Playwright Chromium...
python -m playwright install chromium
if errorlevel 1 goto error
if not exist config.json copy config.example.json config.json >nul
echo.
echo Done. Please edit config.json and replace YOUR_UID with your own uid.
pause
exit /b 0

:error
echo.
echo Setup failed. Please make sure Python is installed and available in PATH.
pause
exit /b 1
