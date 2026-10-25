@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
title HyperGrad market maker
:loop
python -m hip3 mm %*
echo Market maker stopped. Restarting in 10 seconds...
timeout /t 10 >nul
goto loop
