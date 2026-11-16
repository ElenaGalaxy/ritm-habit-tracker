@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not defined PORT set "PORT=5000"

if not exist ".venv\Scripts\python.exe" goto no_venv

echo.
echo   Habit Tracker "Ritm"
echo   URL: http://127.0.0.1:%PORT%
echo   Stop: Ctrl+C
echo.

if not defined NO_BROWSER start "" /min cmd /c "timeout /t 2 >nul & start http://127.0.0.1:%PORT%"

".venv\Scripts\python.exe" app.py
if errorlevel 1 goto server_error
exit /b 0

:server_error
echo.
echo [Error] Server stopped. See the message above.
pause
exit /b 1

:no_venv
echo.
echo [Error] .venv not found.
echo Create it with:
echo   python -m venv .venv
echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
pause
exit /b 1
