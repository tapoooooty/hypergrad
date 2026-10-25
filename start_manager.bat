@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
title HyperGrad manager
:loop
python -m hip3 manager
echo Manager stopped. Restarting in 10 seconds...
timeout /t 10 >nul
goto loop
