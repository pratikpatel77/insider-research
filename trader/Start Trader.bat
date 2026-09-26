@echo off
REM Starts the Insider Trader. Keep this window open while you want the daily routine to run.
cd /d "%~dp0"
python main.py
pause
