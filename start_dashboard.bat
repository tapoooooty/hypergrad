@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
start "" http://localhost:8787
python -m hip3 serve
pause
