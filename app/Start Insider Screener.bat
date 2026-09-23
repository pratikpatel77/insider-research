@echo off
title Insider Buy Screener
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1
where python >nul 2>nul || (echo Python is not installed. Install it from https://www.python.org/downloads/ and tick "Add Python to PATH". & pause & exit /b)
python -c "import requests, pandas, openpyxl" 2>nul || (echo Installing required packages, one time only... & python -m pip install --user requests pandas openpyxl)
python app.py
pause
