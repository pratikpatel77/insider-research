@echo off
REM One-time setup: installs the Python packages. Needs Python 3.10+ (python.org) on PATH.
cd /d "%~dp0"
python --version || (echo Python is not installed. Get it from python.org and tick "Add to PATH". & pause & exit /b 1)
python -m pip install -r requirements.txt
echo.
set /p B=Which live broker will you use? (definedge / kotak / fyers / none) [none]: 
if /i "%B%"=="kotak" python -m pip install kotakneoapi==3.0.6
if /i "%B%"=="fyers" python -m pip install fyers-apiv3==3.1.17
if not exist ".env" copy ".env.example" ".env" >nul
echo.
echo Done. Fill in the credentials for your broker in trader\.env (only needed for live trading),
echo then double-click "Start Trader.bat". It starts in PAPER mode.
pause
