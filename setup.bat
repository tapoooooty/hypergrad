@echo off
cd /d "%~dp0"
where python >nul 2>nul || (echo Install Python 3.10+ from python.org and tick "Add python.exe to PATH". & pause & exit /b 1)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env >nul
echo.
echo Setup complete. Open .env, add your keys, then use the start_*.bat scripts.
pause
