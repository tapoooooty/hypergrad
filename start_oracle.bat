@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
title HyperGrad oracle
:loop
python -m hip3 oracle %*
echo Oracle stopped. Restarting in 3 seconds...
timeout /t 3 >nul
goto loop
