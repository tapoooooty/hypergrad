@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
echo Chats that messaged your bot (send it any message first):
python -m hip3 tg-chatid
echo.
echo Sending a test alert:
python -m hip3 tg-test
pause
