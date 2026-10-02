@echo off
setlocal
cd /d "%~dp0"
python easonfans_daily.py --check-login
pause
