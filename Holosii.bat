@echo off
rem Holosii without the app window: starts the server and opens the browser.
cd /d "%~dp0"
where py >nul 2>nul && (py -3 -X utf8 server.py & goto :eof)
python -X utf8 server.py
